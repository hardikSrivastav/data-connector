const { Tool } = require('@langchain/core/tools');
const fs = require('fs').promises;
const path = require('path');

/**
 * Tool for introspecting (reading) deployment files
 */
class IntrospectFileTool extends Tool {
  constructor() {
    super();
    this.name = 'introspect_file';
    this.description = `
      Read and inspect the contents of a deployment file.
      Input should be a JSON object with:
      - filePath: relative path to the file to inspect (e.g., "config.yaml", "docker-compose.yml")
      Returns the file contents as a string.
    `;
  }

  async _call(input) {
    const readStartTime = Date.now();
    let logContext = {
      tool: 'introspect_file',
      timestamp: new Date().toISOString(),
      filePath: null,
      fullPath: null,
      contentLength: 0,
      success: false,
      duration: 0,
      error: null
    };

    try {
      const { filePath } = JSON.parse(input);
      
      logContext.filePath = filePath;
      
      console.log(`👀 [INTROSPECT_FILE] Starting file read operation:`, {
        file: filePath,
        timestamp: logContext.timestamp
      });

      if (!filePath) {
        logContext.error = 'filePath is required';
        console.error(`❌ [INTROSPECT_FILE] Error:`, logContext.error);
        return 'Error: filePath is required';
      }

      // Security: only allow certain file extensions and no path traversal
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(filePath);
      
      if (!allowedExtensions.includes(ext)) {
        logContext.error = `File extension ${ext} not allowed`;
        console.error(`❌ [INTROSPECT_FILE] Security error:`, {
          error: logContext.error,
          allowedExtensions: allowedExtensions
        });
        return `Error: File extension ${ext} not allowed. Allowed: ${allowedExtensions.join(', ')}`;
      }

      if (filePath.includes('..') || filePath.includes('~')) {
        logContext.error = 'Path traversal not allowed';
        console.error(`❌ [INTROSPECT_FILE] Security error:`, logContext.error);
        return 'Error: Path traversal not allowed';
      }

      // Define the base directory for deployment files
      const baseDir = path.join(__dirname, '..', 'deploy-reference');
      const fullPath = path.join(baseDir, filePath);
      logContext.fullPath = fullPath;

      console.log(`📁 [INTROSPECT_FILE] Resolved file path:`, {
        baseDir: baseDir,
        fullPath: fullPath
      });

      // Check if file exists
      try {
        await fs.access(fullPath);
        console.log(`✅ [INTROSPECT_FILE] File exists and is accessible: ${fullPath}`);
      } catch (error) {
        logContext.error = `File ${filePath} not found`;
        console.error(`❌ [INTROSPECT_FILE] File access error:`, {
          file: fullPath,
          error: error.message
        });
        return `Error: File ${filePath} not found`;
      }

      // Read and return file contents
      const content = await fs.readFile(fullPath, 'utf8');
      logContext.contentLength = content.length;
      logContext.success = true;
      logContext.duration = Date.now() - readStartTime;

      console.log(`📖 [INTROSPECT_FILE] Successfully read file:`, {
        file: filePath,
        contentLength: content.length,
        duration: `${logContext.duration}ms`,
        contentPreview: content.substring(0, 200) + (content.length > 200 ? '...' : '')
      });

      const result = `File: ${filePath}\n\nContents:\n${content}`;
      
      console.log(`✅ [INTROSPECT_FILE] Operation completed successfully:`, {
        file: filePath,
        contentLength: content.length,
        duration: `${logContext.duration}ms`
      });

      return result;

    } catch (parseError) {
      logContext.error = `Parse error: ${parseError.message}`;
      logContext.duration = Date.now() - readStartTime;
      
      console.error(`❌ [INTROSPECT_FILE] Parse error:`, {
        error: parseError.message,
        duration: `${logContext.duration}ms`,
        rawInput: input.substring(0, 200) + (input.length > 200 ? '...' : ''),
        context: logContext
      });
      
      return `Error parsing input: ${parseError.message}. Expected JSON with filePath property.`;
    } finally {
      // Always log the final context for debugging
      console.log(`📋 [INTROSPECT_FILE] Final operation context:`, logContext);
    }
  }
}

/**
 * Tool for editing deployment files with user information
 */
class EditFileTool extends Tool {
  constructor() {
    super();
    this.name = 'edit_file';
    this.description = `
      Edit a deployment file by replacing placeholders with actual values.
      Input should be a JSON object with:
      - filePath: relative path to the file to edit (e.g., "config.yaml")
      - replacements: object with placeholder -> value mappings
      - backup: boolean (default true) whether to create a backup
      Returns success/error message.
    `;
  }

  async _call(input) {
    const editStartTime = Date.now();
    let logContext = {
      tool: 'edit_file',
      timestamp: new Date().toISOString(),
      filePath: null,
      fullPath: null,
      backupPath: null,
      replacements: {},
      originalContentLength: 0,
      modifiedContentLength: 0,
      replacementsMade: [],
      totalReplacements: 0,
      success: false,
      duration: 0,
      error: null
    };

    try {
      // Parse and validate input
      const { filePath, replacements, backup = true } = JSON.parse(input);
      
      logContext.filePath = filePath;
      logContext.replacements = replacements;
      
      console.log(`🔧 [EDIT_FILE] Starting edit operation:`, {
        file: filePath,
        replacements: Object.keys(replacements || {}),
        backup: backup,
        timestamp: logContext.timestamp
      });

      if (!filePath || !replacements) {
        logContext.error = 'Missing required parameters';
        console.error(`❌ [EDIT_FILE] Error:`, logContext.error);
        return 'Error: Both filePath and replacements are required';
      }

      // Security checks (same as introspect tool)
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(filePath);
      
      if (!allowedExtensions.includes(ext)) {
        logContext.error = `File extension ${ext} not allowed`;
        console.error(`❌ [EDIT_FILE] Security error:`, logContext.error);
        return `Error: File extension ${ext} not allowed`;
      }

      if (filePath.includes('..') || filePath.includes('~')) {
        logContext.error = 'Path traversal not allowed';
        console.error(`❌ [EDIT_FILE] Security error:`, logContext.error);
        return 'Error: Path traversal not allowed';
      }

      const baseDir = path.join(__dirname, '..', 'deploy-reference');
      const fullPath = path.join(baseDir, filePath);
      logContext.fullPath = fullPath;

      console.log(`📁 [EDIT_FILE] Resolved file path:`, {
        baseDir: baseDir,
        fullPath: fullPath
      });

      // Check if file exists
      try {
        await fs.access(fullPath);
        console.log(`✅ [EDIT_FILE] File exists and is accessible: ${fullPath}`);
      } catch (error) {
        logContext.error = `File ${filePath} not found`;
        console.error(`❌ [EDIT_FILE] File access error:`, {
          file: fullPath,
          error: error.message
        });
        return `Error: File ${filePath} not found`;
      }

      // Read current content
      let originalContent = await fs.readFile(fullPath, 'utf8');
      logContext.originalContentLength = originalContent.length;
      
      console.log(`📖 [EDIT_FILE] Read original content:`, {
        file: filePath,
        contentLength: originalContent.length,
        contentPreview: originalContent.substring(0, 200) + (originalContent.length > 200 ? '...' : '')
      });

      // Create backup if requested
      let backupPath = null;
      if (backup) {
        backupPath = `${fullPath}.backup.${Date.now()}`;
        logContext.backupPath = backupPath;
        await fs.writeFile(backupPath, originalContent);
        console.log(`💾 [EDIT_FILE] Created backup:`, {
          originalFile: fullPath,
          backupFile: backupPath,
          backupSize: originalContent.length
        });
      }

      // Apply replacements with detailed logging
      let modifiedContent = originalContent;
      let totalReplacements = 0;
      const replacementDetails = [];

      console.log(`🔄 [EDIT_FILE] Starting replacements:`, {
        totalReplacementRules: Object.keys(replacements).length
      });

      for (const [placeholder, value] of Object.entries(replacements)) {
        const regex = new RegExp(placeholder, 'g');
        const matches = modifiedContent.match(regex);
        
        if (matches) {
          const beforeLength = modifiedContent.length;
          modifiedContent = modifiedContent.replace(regex, value);
          const afterLength = modifiedContent.length;
          const replacementCount = matches.length;
          totalReplacements += replacementCount;

          const replacementDetail = {
            placeholder: placeholder,
            value: value,
            occurrences: replacementCount,
            lengthChange: afterLength - beforeLength
          };
          
          replacementDetails.push(replacementDetail);
          logContext.replacementsMade.push(replacementDetail);

          console.log(`✏️  [EDIT_FILE] Applied replacement:`, {
            placeholder: placeholder,
            value: typeof value === 'string' && value.length > 50 ? value.substring(0, 50) + '...' : value,
            occurrences: replacementCount,
            lengthChange: afterLength - beforeLength
          });
        } else {
          console.log(`⚠️  [EDIT_FILE] No matches found for placeholder: ${placeholder}`);
        }
      }

      logContext.totalReplacements = totalReplacements;
      logContext.modifiedContentLength = modifiedContent.length;

      console.log(`📊 [EDIT_FILE] Replacement summary:`, {
        totalReplacements: totalReplacements,
        originalLength: originalContent.length,
        modifiedLength: modifiedContent.length,
        lengthDifference: modifiedContent.length - originalContent.length,
        replacementDetails: replacementDetails
      });

      // Write updated content
      await fs.writeFile(fullPath, modifiedContent);
      
      console.log(`💾 [EDIT_FILE] Wrote modified content:`, {
        file: fullPath,
        newSize: modifiedContent.length,
        modifiedContentPreview: modifiedContent.substring(0, 200) + (modifiedContent.length > 200 ? '...' : '')
      });

      // Calculate duration and mark success
      logContext.duration = Date.now() - editStartTime;
      logContext.success = true;

      const successMessage = `Successfully updated ${filePath}. Made ${totalReplacements} replacements.${backup ? ' Backup created.' : ''}`;
      
      console.log(`✅ [EDIT_FILE] Operation completed successfully:`, {
        file: filePath,
        totalReplacements: totalReplacements,
        duration: `${logContext.duration}ms`,
        backup: backup ? backupPath : 'no backup',
        finalSummary: {
          originalSize: originalContent.length,
          finalSize: modifiedContent.length,
          totalChanges: totalReplacements,
          backupCreated: !!backup
        }
      });

      return successMessage;

    } catch (parseError) {
      logContext.error = `Parse error: ${parseError.message}`;
      logContext.duration = Date.now() - editStartTime;
      
      console.error(`❌ [EDIT_FILE] Parse error:`, {
        error: parseError.message,
        duration: `${logContext.duration}ms`,
        rawInput: input.substring(0, 200) + (input.length > 200 ? '...' : ''),
        context: logContext
      });
      
      return `Error parsing input: ${parseError.message}. Expected JSON with filePath and replacements properties.`;
    } finally {
      // Always log the final context for debugging
      console.log(`📋 [EDIT_FILE] Final operation context:`, logContext);
    }
  }
}

/**
 * Tool for listing available deployment files
 */
class ListDeploymentFilesTool extends Tool {
  constructor() {
    super();
    this.name = 'list_deployment_files';
    this.description = `
      List all available deployment files in the deploy directory.
      No input required.
      Returns a list of available files.
    `;
  }

  async _call(input) {
    try {
      const baseDir = path.join(__dirname, '..', 'deploy-reference');
      
      const files = await fs.readdir(baseDir);
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      
      const deploymentFiles = files
        .filter(file => allowedExtensions.includes(path.extname(file)))
        .sort();

      return `Available deployment files:\n${deploymentFiles.map(f => `- ${f}`).join('\n')}`;

    } catch (error) {
      return `Error listing files: ${error.message}`;
    }
  }
}

/**
 * Tool for creating new deployment files from templates
 */
class CreateDeploymentFileTool extends Tool {
  constructor() {
    super();
    this.name = 'create_deployment_file';
    this.description = `
      Create a new deployment file from a template.
      Input should be a JSON object with:
      - fileName: name of the file to create (e.g., "custom-config.yaml")
      - template: the template content as a string
      - overwrite: boolean (default false) whether to overwrite if exists
      Returns success/error message.
    `;
  }

  async _call(input) {
    const createStartTime = Date.now();
    let logContext = {
      tool: 'create_deployment_file',
      timestamp: new Date().toISOString(),
      fileName: null,
      fullPath: null,
      templateLength: 0,
      fileExisted: false,
      overwrite: false,
      success: false,
      duration: 0,
      error: null
    };

    try {
      const { fileName, template, overwrite = false } = JSON.parse(input);
      
      logContext.fileName = fileName;
      logContext.templateLength = template ? template.length : 0;
      logContext.overwrite = overwrite;
      
      console.log(`🆕 [CREATE_FILE] Starting file creation operation:`, {
        fileName: fileName,
        templateLength: template ? template.length : 0,
        overwrite: overwrite,
        timestamp: logContext.timestamp
      });

      if (!fileName || !template) {
        logContext.error = 'Both fileName and template are required';
        console.error(`❌ [CREATE_FILE] Error:`, logContext.error);
        return 'Error: Both fileName and template are required';
      }

      // Security checks
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(fileName);
      
      if (!allowedExtensions.includes(ext)) {
        logContext.error = `File extension ${ext} not allowed`;
        console.error(`❌ [CREATE_FILE] Security error:`, {
          error: logContext.error,
          allowedExtensions: allowedExtensions
        });
        return `Error: File extension ${ext} not allowed`;
      }

      if (fileName.includes('..') || fileName.includes('~') || fileName.includes('/')) {
        logContext.error = 'Invalid file name - path separators/traversal not allowed';
        console.error(`❌ [CREATE_FILE] Security error:`, logContext.error);
        return 'Error: Invalid file name. No path separators or traversal allowed';
      }

      const baseDir = path.join(__dirname, '..', 'deploy-reference');
      const fullPath = path.join(baseDir, fileName);
      logContext.fullPath = fullPath;

      console.log(`📁 [CREATE_FILE] Resolved file path:`, {
        baseDir: baseDir,
        fullPath: fullPath
      });

      // Check if file exists and overwrite policy
      try {
        await fs.access(fullPath);
        logContext.fileExisted = true;
        
        console.log(`⚠️  [CREATE_FILE] File already exists:`, {
          file: fullPath,
          overwrite: overwrite
        });
        
        if (!overwrite) {
          logContext.error = `File ${fileName} already exists and overwrite=false`;
          console.error(`❌ [CREATE_FILE] Error:`, logContext.error);
          return `Error: File ${fileName} already exists. Set overwrite=true to replace it.`;
        }
        
        console.log(`🔄 [CREATE_FILE] Will overwrite existing file: ${fileName}`);
      } catch (error) {
        // File doesn't exist, which is fine for new files
        console.log(`✅ [CREATE_FILE] File doesn't exist, ready to create new file: ${fileName}`);
      }

      console.log(`📝 [CREATE_FILE] Writing template content:`, {
        file: fileName,
        templateLength: template.length,
        templatePreview: template.substring(0, 200) + (template.length > 200 ? '...' : '')
      });

      // Write the template content
      await fs.writeFile(fullPath, template);
      
      logContext.success = true;
      logContext.duration = Date.now() - createStartTime;

      const successMessage = `Successfully created ${fileName}`;
      
      console.log(`✅ [CREATE_FILE] Operation completed successfully:`, {
        fileName: fileName,
        fullPath: fullPath,
        templateLength: template.length,
        duration: `${logContext.duration}ms`,
        fileExisted: logContext.fileExisted,
        overwrite: overwrite
      });

      return successMessage;

    } catch (parseError) {
      logContext.error = `Parse error: ${parseError.message}`;
      logContext.duration = Date.now() - createStartTime;
      
      console.error(`❌ [CREATE_FILE] Parse error:`, {
        error: parseError.message,
        duration: `${logContext.duration}ms`,
        rawInput: input.substring(0, 200) + (input.length > 200 ? '...' : ''),
        context: logContext
      });
      
      return `Error parsing input: ${parseError.message}. Expected JSON with fileName and template properties.`;
    } finally {
      // Always log the final context for debugging
      console.log(`📋 [CREATE_FILE] Final operation context:`, logContext);
    }
  }
}

/**
 * Tool for packaging deployment files for download
 */
class PackageDeploymentFilesTool extends Tool {
  constructor() {
    super();
    this.name = 'package_deployment_files';
    this.description = `
      Package all deployment files for download when deployment is 100% complete.
      Input should be a JSON object with:
      - packageName: name for the deployment package (e.g., "ceneca-deployment")
      - includeBackups: boolean (default false) whether to include backup files
      Returns package information and download details.
    `;
  }

  async _call(input) {
    try {
      const { packageName = 'ceneca-deployment', includeBackups = false } = JSON.parse(input);
      
      const baseDir = path.join(__dirname, '..', 'deploy-reference');
      const packageDir = path.join(__dirname, '..', 'packages');
      
      // Ensure packages directory exists
      try {
        await fs.mkdir(packageDir, { recursive: true });
      } catch (error) {
        // Directory might already exist
      }

      // Get all deployment files
      const files = await fs.readdir(baseDir);
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh', '.md'];
      
      let deploymentFiles = files.filter(file => {
        const ext = path.extname(file);
        const isAllowed = allowedExtensions.includes(ext);
        const isBackup = file.includes('.backup.');
        
        if (includeBackups) {
          return isAllowed;
        } else {
          return isAllowed && !isBackup;
        }
      });

      if (deploymentFiles.length === 0) {
        return 'Error: No deployment files found to package';
      }

      // Create package timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
      const packageId = `${packageName}-${timestamp}`;
      const packagePath = path.join(packageDir, packageId);
      
      // Create package directory
      await fs.mkdir(packagePath, { recursive: true });

      // Copy files to package directory
      const copiedFiles = [];
      for (const file of deploymentFiles) {
        try {
          const sourcePath = path.join(baseDir, file);
          const destPath = path.join(packagePath, file);
          
          const content = await fs.readFile(sourcePath);
          await fs.writeFile(destPath, content);
          
          copiedFiles.push(file);
        } catch (error) {
          console.warn(`Failed to copy ${file}: ${error.message}`);
        }
      }

      // Create package manifest
      const manifest = {
        packageName: packageId,
        createdAt: new Date().toISOString(),
        files: copiedFiles,
        totalFiles: copiedFiles.length,
        downloadPath: `/api/download/${packageId}`
      };

      await fs.writeFile(
        path.join(packagePath, 'package-manifest.json'), 
        JSON.stringify(manifest, null, 2)
      );

      return `Deployment package created successfully!

Package Details:
- Package ID: ${packageId}
- Files included: ${copiedFiles.length}
- Files: ${copiedFiles.join(', ')}

Your deployment package is ready for download. The package contains all your configured deployment files and is ready for immediate deployment.`;

    } catch (parseError) {
      return `Error creating package: ${parseError.message}`;
    }
  }
}

module.exports = {
  IntrospectFileTool,
  EditFileTool,
  ListDeploymentFilesTool,
  CreateDeploymentFileTool,
  PackageDeploymentFilesTool
}; 