"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { Download, Shield, Server, Database, Key, CheckCircle, Clock, FileText, MessageCircle } from "lucide-react";
import Link from "next/link";

interface DeploymentFile {
  name: string;
  description: string;
  size: string;
  type: 'required' | 'optional' | 'documentation';
  icon: React.ReactNode;
}

const deploymentFiles: DeploymentFile[] = [
  {
    name: "docker-compose.yml",
    description: "Main deployment configuration with health checks and volumes",
    size: "2.4 KB",
    type: "required",
    icon: <Server className="h-4 w-4" />
  },
  {
    name: "Dockerfile",
    description: "Multi-stage build for React frontend and Python backend",
    size: "3.1 KB", 
    type: "required",
    icon: <Server className="h-4 w-4" />
  },
  {
    name: "nginx.conf",
    description: "Production web server config with SSL and security headers",
    size: "1.8 KB",
    type: "required",
    icon: <Shield className="h-4 w-4" />
  },
  {
    name: "config.yaml.example",
    description: "Database and system configuration template",
    size: "1.2 KB",
    type: "required",
    icon: <Database className="h-4 w-4" />
  },
  {
    name: "auth-config.yaml.example",
    description: "SSO configuration for Okta/Azure/Google/Auth0",
    size: "0.9 KB",
    type: "required",
    icon: <Key className="h-4 w-4" />
  },
  {
    name: "setup.sh",
    description: "Interactive configuration wizard",
    size: "2.7 KB",
    type: "optional",
    icon: <CheckCircle className="h-4 w-4" />
  },
  {
    name: "test-deployment.sh",
    description: "Comprehensive deployment validation with colored output",
    size: "3.5 KB",
    type: "optional",
    icon: <CheckCircle className="h-4 w-4" />
  },
  {
    name: "README.md",
    description: "Customer-facing setup guide with 5-step process",
    size: "4.2 KB",
    type: "documentation",
    icon: <FileText className="h-4 w-4" />
  },
  {
    name: "QUICK_TEST.md",
    description: "5-minute testing guide for validation",
    size: "1.1 KB",
    type: "documentation",
    icon: <FileText className="h-4 w-4" />
  }
];

export default function DeploymentPortal() {
  const [licenseKey, setLicenseKey] = useState("");
  const [customerInfo, setCustomerInfo] = useState({
    company: "",
    email: "",
    environment: ""
  });
  const [isValidated, setIsValidated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleLicenseValidation = async () => {
    if (!licenseKey.trim()) {
      toast.error("Please enter your license key");
      return;
    }

    setIsLoading(true);
    
    try {
      // Simulate license validation
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock successful validation
      setIsValidated(true);
      setCustomerInfo({
        company: "Acme Corporation",
        email: "admin@acmecorp.com",
        environment: "Production"
      });
      
      toast.success("License validated successfully!");
    } catch (error) {
      toast.error("Invalid license key. Please contact support.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileDownload = async (fileName: string) => {
    try {
      // Call API to download specific file
      const response = await fetch(`/api/deployment/download/${fileName}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${licenseKey}`
        }
      });

      if (!response.ok) {
        throw new Error('Download failed');
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      window.URL.revokeObjectURL(url);
      
      toast.success(`${fileName} downloaded successfully`);
    } catch (error) {
      toast.error(`Failed to download ${fileName}`);
    }
  };

  const handleDownloadAll = async () => {
    try {
      // Call API to download complete package
      const response = await fetch(`/api/deployment/download/package`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${licenseKey}`
        }
      });

      if (!response.ok) {
        throw new Error('Download failed');
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'ceneca-deployment-package.zip';
      a.click();
      window.URL.revokeObjectURL(url);
      
      toast.success("Complete deployment package downloaded!");
    } catch (error) {
      toast.error("Failed to download deployment package");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background/95 to-muted/10">
      <div className="container mx-auto px-4 py-8 pt-32">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-4 font-baskerville">Ceneca Deployment Portal</h1>
            <p className="text-lg text-muted-foreground font-baskerville">
              Download your enterprise deployment package for on-premise installation
            </p>
            <div className="mt-4">
              <Link href="/deployment/chat">
                <Button variant="outline" className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300">
                  <MessageCircle className="h-4 w-4 mr-2" />
                  Try Our AI Configuration Assistant
                </Button>
              </Link>
            </div>
          </div>

          {/* License Validation */}
          {!isValidated && (
            <Card className="mb-8 bg-card/50 backdrop-blur-sm border border-muted rounded-xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-baskerville">
                  <Key className="h-5 w-5" />
                  License Validation
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="license" className="text-sm font-medium font-baskerville">
                    Enter your license key
                  </label>
                  <Input
                    id="license"
                    type="text"
                    value={licenseKey}
                    onChange={(e) => setLicenseKey(e.target.value)}
                    placeholder="CENECA-XXXX-XXXX-XXXX"
                    className="h-10 bg-background/80 border-muted font-baskerville"
                  />
                  <div className="text-xs text-muted-foreground font-baskerville">
                    <p className="mb-1">Valid formats:</p>
                    <ul className="space-y-1">
                      <li>• Production: <code className="bg-muted px-1 rounded font-baskerville">CENECA-XXXX-XXXX-XXXX</code></li>
                      <li>• Testing: <code className="bg-muted px-1 rounded font-baskerville">demo-license</code>, <code className="bg-muted px-1 rounded font-baskerville">test-license</code>, <code className="bg-muted px-1 rounded font-baskerville">test-123</code></li>
                    </ul>
                  </div>
                </div>
                <Button
                  onClick={handleLicenseValidation}
                  disabled={isLoading}
                  className="w-full h-10 text-white bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 animate-spin" />
                      Validating...
                    </div>
                  ) : (
                    "Validate License"
                  )}
                </Button>
                <p className="text-sm text-muted-foreground text-center font-baskerville">
                  Don't have a license key? <a href="/contact" className="text-primary hover:underline font-baskerville">Contact our sales team</a>
                </p>
              </CardContent>
            </Card>
          )}

          {/* Customer Information */}
          {isValidated && (
            <Card className="mb-8 bg-card/50 backdrop-blur-sm border border-muted rounded-xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-baskerville">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  License Validated
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground font-baskerville">Company</p>
                    <p className="font-medium font-baskerville">{customerInfo.company}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground font-baskerville">Email</p>
                    <p className="font-medium font-baskerville">{customerInfo.email}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground font-baskerville">Environment</p>
                    <p className="font-medium font-baskerville">{customerInfo.environment}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Download Section */}
          {isValidated && (
            <>
              {/* Quick Download */}
              <Card className="mb-8 bg-card/50 backdrop-blur-sm border border-muted rounded-xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 font-baskerville">
                    <Download className="h-5 w-5" />
                    Quick Download
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col sm:flex-row gap-4">
                    <Button
                      onClick={handleDownloadAll}
                      className="flex-1 h-12 text-white bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Download Complete Package
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Individual Files */}
              <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 font-baskerville">
                    <FileText className="h-5 w-5" />
                    Individual Files
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Required Files */}
                    <div>
                      <h3 className="font-medium mb-3 flex items-center gap-2 font-baskerville">
                        <Badge variant="outline">Required</Badge>
                        Core Deployment Files
                      </h3>
                      <div className="grid gap-2">
                        {deploymentFiles.filter(f => f.type === 'required').map((file) => (
                          <div
                            key={file.name}
                            className="flex items-center justify-between p-3 bg-background/50 rounded-lg border border-muted/50"
                          >
                            <div className="flex items-center gap-3">
                              {file.icon}
                              <div>
                                <p className="font-medium font-baskerville">{file.name}</p>
                                <p className="text-sm text-muted-foreground font-baskerville">{file.description}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-muted-foreground font-baskerville">{file.size}</span>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleFileDownload(file.name)}
                                className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300"
                              >
                                <Download className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <Separator />

                    {/* Optional Files */}
                    <div>
                      <h3 className="font-medium mb-3 flex items-center gap-2 font-baskerville">
                        <Badge variant="outline">Optional</Badge>
                        Setup & Testing Scripts
                      </h3>
                      <div className="grid gap-2">
                        {deploymentFiles.filter(f => f.type === 'optional').map((file) => (
                          <div
                            key={file.name}
                            className="flex items-center justify-between p-3 bg-background/50 rounded-lg border border-muted/50"
                          >
                            <div className="flex items-center gap-3">
                              {file.icon}
                              <div>
                                <p className="font-medium font-baskerville">{file.name}</p>
                                <p className="text-sm text-muted-foreground font-baskerville">{file.description}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-muted-foreground font-baskerville">{file.size}</span>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleFileDownload(file.name)}
                                className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300"
                              >
                                <Download className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <Separator />

                    {/* Documentation */}
                    <div>
                      <h3 className="font-medium mb-3 flex items-center gap-2 font-baskerville">
                        <Badge variant="outline">Documentation</Badge>
                        Setup Guides
                      </h3>
                      <div className="grid gap-2">
                        {deploymentFiles.filter(f => f.type === 'documentation').map((file) => (
                          <div
                            key={file.name}
                            className="flex items-center justify-between p-3 bg-background/50 rounded-lg border border-muted/50"
                          >
                            <div className="flex items-center gap-3">
                              {file.icon}
                              <div>
                                <p className="font-medium font-baskerville">{file.name}</p>
                                <p className="text-sm text-muted-foreground font-baskerville">{file.description}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-muted-foreground font-baskerville">{file.size}</span>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleFileDownload(file.name)}
                                className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300"
                              >
                                <Download className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Support Information */}
              <Card className="mt-8 bg-card/50 backdrop-blur-sm border border-muted rounded-xl">
                <CardHeader>
                  <CardTitle className="font-baskerville">Need Help?</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-medium mb-2 font-baskerville">Technical Support</h4>
                      <p className="text-sm text-muted-foreground mb-2 font-baskerville">
                        Get help with deployment and configuration
                      </p>
                      <Button variant="outline" size="sm" className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300">
                        Contact Support
                      </Button>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2 font-baskerville">Documentation</h4>
                      <p className="text-sm text-muted-foreground mb-2 font-baskerville">
                        Comprehensive guides and API references
                      </p>
                      <Button variant="outline" size="sm" className="font-baskerville hover:bg-[#7b35b8] hover:text-white transition-all duration-300">
                        View Docs
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
} 