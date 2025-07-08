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
    try {
      const { filePath } = JSON.parse(input);
      
      if (!filePath) {
        return 'Error: filePath is required';
      }

      // Security: only allow certain file extensions and no path traversal
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(filePath);
      
      if (!allowedExtensions.includes(ext)) {
        return `Error: File extension ${ext} not allowed. Allowed: ${allowedExtensions.join(', ')}`;
      }

      if (filePath.includes('..') || filePath.includes('~')) {
        return 'Error: Path traversal not allowed';
      }

      // Define the base directory for deployment files
      const baseDir = path.join(__dirname, '../../..', 'deploy');
      const fullPath = path.join(baseDir, filePath);

      // Check if file exists
      try {
        await fs.access(fullPath);
      } catch (error) {
        return `Error: File ${filePath} not found`;
      }

      // Read and return file contents
      const content = await fs.readFile(fullPath, 'utf8');
      return `File: ${filePath}\n\nContents:\n${content}`;

    } catch (parseError) {
      return `Error parsing input: ${parseError.message}. Expected JSON with filePath property.`;
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
    try {
      const { filePath, replacements, backup = true } = JSON.parse(input);
      
      if (!filePath || !replacements) {
        return 'Error: Both filePath and replacements are required';
      }

      // Security checks (same as introspect tool)
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(filePath);
      
      if (!allowedExtensions.includes(ext)) {
        return `Error: File extension ${ext} not allowed`;
      }

      if (filePath.includes('..') || filePath.includes('~')) {
        return 'Error: Path traversal not allowed';
      }

      const baseDir = path.join(__dirname, '../../..', 'deploy');
      const fullPath = path.join(baseDir, filePath);

      // Check if file exists
      try {
        await fs.access(fullPath);
      } catch (error) {
        return `Error: File ${filePath} not found`;
      }

      // Read current content
      let content = await fs.readFile(fullPath, 'utf8');

      // Create backup if requested
      if (backup) {
        const backupPath = `${fullPath}.backup.${Date.now()}`;
        await fs.writeFile(backupPath, content);
      }

      // Apply replacements
      let replacementCount = 0;
      for (const [placeholder, value] of Object.entries(replacements)) {
        const regex = new RegExp(placeholder, 'g');
        const matches = content.match(regex);
        if (matches) {
          content = content.replace(regex, value);
          replacementCount += matches.length;
        }
      }

      // Write updated content
      await fs.writeFile(fullPath, content);

      return `Successfully updated ${filePath}. Made ${replacementCount} replacements.${backup ? ' Backup created.' : ''}`;

    } catch (parseError) {
      return `Error parsing input: ${parseError.message}. Expected JSON with filePath and replacements properties.`;
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
      const baseDir = path.join(__dirname, '../../..', 'deploy');
      
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
    try {
      const { fileName, template, overwrite = false } = JSON.parse(input);
      
      if (!fileName || !template) {
        return 'Error: Both fileName and template are required';
      }

      // Security checks
      const allowedExtensions = ['.yaml', '.yml', '.json', '.conf', '.env', '.sh'];
      const ext = path.extname(fileName);
      
      if (!allowedExtensions.includes(ext)) {
        return `Error: File extension ${ext} not allowed`;
      }

      if (fileName.includes('..') || fileName.includes('~') || fileName.includes('/')) {
        return 'Error: Invalid file name. No path separators or traversal allowed';
      }

      const baseDir = path.join(__dirname, '../../..', 'deploy');
      const fullPath = path.join(baseDir, fileName);

      // Check if file exists and overwrite policy
      try {
        await fs.access(fullPath);
        if (!overwrite) {
          return `Error: File ${fileName} already exists. Set overwrite=true to replace it.`;
        }
      } catch (error) {
        // File doesn't exist, which is fine for new files
      }

      // Write the template content
      await fs.writeFile(fullPath, template);

      return `Successfully created ${fileName}`;

    } catch (parseError) {
      return `Error parsing input: ${parseError.message}. Expected JSON with fileName and template properties.`;
    }
  }
}

module.exports = {
  IntrospectFileTool,
  EditFileTool,
  ListDeploymentFilesTool,
  CreateDeploymentFileTool
}; 