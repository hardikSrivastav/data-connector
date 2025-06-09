import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { 
  RefreshCw, 
  CheckCircle,
  XCircle,
  ArrowLeft
} from 'lucide-react';
import { agentClient, DatabaseStatus, DatabaseAvailabilityResponse } from '@/lib/agent-client';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useNavigate } from 'react-router-dom';

interface UserPreferences {
  enableNotifications: boolean;
  autoSaveQueries: boolean;
  defaultAnalyzeMode: boolean;
  pollInterval: number;
  enableLiveUpdates: boolean;
  showAdvancedSettings: boolean;
}

export const Settings = () => {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [databaseData, setDatabaseData] = useState<DatabaseAvailabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({
    enableNotifications: true,
    autoSaveQueries: true,
    defaultAnalyzeMode: false,
    pollInterval: 30,
    enableLiveUpdates: true,
    showAdvancedSettings: false
  });

  // Load database availability on component mount
  useEffect(() => {
    loadDatabaseAvailability();
    
    // Set up polling for live updates if enabled
    const interval = setInterval(() => {
      if (preferences.enableLiveUpdates) {
        loadDatabaseAvailability(true);
      }
    }, preferences.pollInterval * 1000);

    return () => clearInterval(interval);
  }, [preferences.enableLiveUpdates, preferences.pollInterval]);

  const loadDatabaseAvailability = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await agentClient.getDatabaseAvailability(user?.id);
      setDatabaseData(data);
    } catch (error) {
      console.error('Failed to load database availability:', error);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleRefreshDatabases = async () => {
    setRefreshing(true);
    try {
      const data = await agentClient.forceDatabaseCheck();
      setDatabaseData(data);
    } catch (error) {
      console.error('Failed to refresh databases:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRefreshSingleDatabase = async (databaseName: string) => {
    try {
      await agentClient.forceDatabaseCheck(databaseName);
      await loadDatabaseAvailability(true);
    } catch (error) {
      console.error(`Failed to refresh database ${databaseName}:`, error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />;
      case 'offline':
        return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
      default:
        return <div className="h-4 w-4 rounded-full bg-muted" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = "inline-flex items-center gap-1";
    switch (status) {
      case 'online':
        return <Badge className={`${baseClasses} bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800`}>Online</Badge>;
      case 'offline':
        return <Badge className={`${baseClasses} bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800`}>Offline</Badge>;
      case 'error':
        return <Badge className={`${baseClasses} bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800`}>Error</Badge>;
      default:
        return <Badge className={`${baseClasses} bg-muted text-muted-foreground border-border`}>Unknown</Badge>;
    }
  };

  const formatLastChecked = (lastChecked: string) => {
    const date = new Date(lastChecked);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const updatePreference = (key: keyof UserPreferences, value: any) => {
    setPreferences(prev => ({ ...prev, [key]: value }));
    // In a real app, this would save to localStorage or backend
    localStorage.setItem('userPreferences', JSON.stringify({ ...preferences, [key]: value }));
  };

  // Load preferences from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('userPreferences');
    if (saved) {
      try {
        setPreferences(JSON.parse(saved));
      } catch (error) {
        console.error('Failed to load user preferences:', error);
      }
    }
  }, []);

  return (
    <div className="container mx-auto p-6 max-w-6xl bg-background text-foreground">
      {/* Navigation Header */}
      <div className="flex items-center gap-3 mb-4">
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={() => navigate('/')}
          className="flex items-center gap-2 hover:bg-accent text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Workspace
        </Button>
      </div>
      
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground">Manage your account, preferences, and database connections</p>
      </div>

      <Tabs defaultValue="databases" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 bg-muted">
          <TabsTrigger value="databases" className="data-[state=active]:bg-card text-foreground">
            Databases
          </TabsTrigger>
          <TabsTrigger value="preferences" className="data-[state=active]:bg-card text-foreground">
            Preferences
          </TabsTrigger>
        </TabsList>

        {/* Database Availability Tab */}
        <TabsContent value="databases" className="space-y-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-foreground">Database Availability</h2>
                <p className="text-sm text-muted-foreground">Monitor and manage connections to your enterprise databases</p>
              </div>
              <Button 
                onClick={handleRefreshDatabases} 
                disabled={refreshing}
                variant="outline"
                size="sm"
                className="border-border hover:bg-accent text-foreground"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''} mr-2`} />
                Refresh All
              </Button>
            </div>
            <div>
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-8 w-8 animate-spin text-blue-600 dark:text-blue-400" />
                  <span className="ml-2 text-muted-foreground">Loading database status...</span>
                </div>
              ) : databaseData ? (
                <div className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="bg-card border-border">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-foreground">{databaseData.summary.total_databases}</p>
                        <span className="text-sm text-muted-foreground">Total</span>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-green-600 dark:text-green-400">{databaseData.summary.online}</p>
                        <span className="text-sm text-muted-foreground">Online</span>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-red-600 dark:text-red-400">{databaseData.summary.offline}</p>
                        <span className="text-sm text-muted-foreground">Offline</span>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                          {databaseData.summary.uptime_percentage.toFixed(0)}%
                        </p>
                        <span className="text-sm text-muted-foreground">Uptime</span>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Database List */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-foreground">Connected Databases</h3>
                      <span className="text-sm text-muted-foreground">
                        {databaseData.databases.length} database{databaseData.databases.length !== 1 ? 's' : ''} configured
                      </span>
                    </div>
                    <div className="grid gap-4">
                      {databaseData.databases.map((db: DatabaseStatus) => (
                        <Card key={db.name} className="bg-card border-border">
                          <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                {getStatusIcon(db.status)}
                                <div>
                                  <CardTitle className="text-lg text-foreground capitalize">{db.name}</CardTitle>
                                  <CardDescription className="text-muted-foreground">
                                    Database connection
                                  </CardDescription>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                {getStatusBadge(db.status)}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRefreshSingleDatabase(db.name)}
                                  className="hover:bg-accent text-muted-foreground"
                                >
                                  <RefreshCw className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="pt-0">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-muted-foreground">Last Checked:</span>
                                <div className="font-medium text-foreground">{formatLastChecked(db.last_checked)}</div>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Response Time:</span>
                                <div className="font-medium text-foreground">
                                  {db.response_time_ms ? `${db.response_time_ms}ms` : 'N/A'}
                                </div>
                              </div>
                            </div>
                            {db.error_message && (
                              <div className="mt-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">
                                {db.error_message}
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="h-12 w-12 bg-muted rounded mx-auto mb-4" />
                  <p className="text-muted-foreground">No database information available</p>
                  <Button onClick={() => loadDatabaseAvailability()} className="mt-4">
                    Load Database Status
                  </Button>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* User Preferences Tab */}
        <TabsContent value="preferences" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                User Preferences
              </CardTitle>
              <CardDescription>
                Customize your experience and default settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Theme Settings */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-foreground">Appearance</h3>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-foreground">Theme</span>
                  <select 
                    value={theme}
                    onChange={(e) => setTheme(e.target.value as 'light' | 'dark' | 'system')}
                    className="border border-border bg-card text-foreground rounded px-3 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                    <option value="system">System</option>
                  </select>
                </div>
              </div>

              <Separator />

              {/* Query Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-foreground">Query Behavior</h3>
                
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Auto-save queries</p>
                    <p className="text-xs text-muted-foreground">Automatically save queries to session history</p>
                  </div>
                  <Switch 
                    checked={preferences.autoSaveQueries}
                    onCheckedChange={(checked) => updatePreference('autoSaveQueries', checked)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Default analyze mode</p>
                    <p className="text-xs text-muted-foreground">Enable analysis by default for new queries</p>
                  </div>
                  <Switch 
                    checked={preferences.defaultAnalyzeMode}
                    onCheckedChange={(checked) => updatePreference('defaultAnalyzeMode', checked)}
                  />
                </div>
              </div>

              <Separator />

              {/* Live Updates */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-foreground">Live Updates</h3>
                
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Enable notifications</p>
                    <p className="text-xs text-muted-foreground">Get notified about query completions and alerts</p>
                  </div>
                  <Switch 
                    checked={preferences.enableNotifications}
                    onCheckedChange={(checked) => updatePreference('enableNotifications', checked)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Live database monitoring</p>
                    <p className="text-xs text-muted-foreground">Automatically refresh database status</p>
                  </div>
                  <Switch 
                    checked={preferences.enableLiveUpdates}
                    onCheckedChange={(checked) => updatePreference('enableLiveUpdates', checked)}
                  />
                </div>

                {preferences.enableLiveUpdates && (
                  <div className="flex items-center justify-between pl-4">
                    <div>
                      <p className="text-sm font-medium text-foreground">Refresh interval</p>
                      <p className="text-xs text-muted-foreground">How often to check database status</p>
                    </div>
                    <select 
                      value={preferences.pollInterval}
                      onChange={(e) => updatePreference('pollInterval', parseInt(e.target.value))}
                      className="border border-border bg-card text-foreground rounded px-3 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value={15}>15 seconds</option>
                      <option value={30}>30 seconds</option>
                      <option value={60}>1 minute</option>
                      <option value={300}>5 minutes</option>
                    </select>
                  </div>
                )}
              </div>

              <Separator />

              {/* Advanced Settings */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Show advanced settings</p>
                    <p className="text-xs text-muted-foreground">Display developer and power-user options</p>
                  </div>
                  <Switch 
                    checked={preferences.showAdvancedSettings}
                    onCheckedChange={(checked) => updatePreference('showAdvancedSettings', checked)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}; 