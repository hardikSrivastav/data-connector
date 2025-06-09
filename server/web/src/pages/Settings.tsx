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
import { useNavigate } from 'react-router-dom';

interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  enableNotifications: boolean;
  autoSaveQueries: boolean;
  defaultAnalyzeMode: boolean;
  pollInterval: number;
  enableLiveUpdates: boolean;
  showAdvancedSettings: boolean;
}

export const Settings = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [databaseData, setDatabaseData] = useState<DatabaseAvailabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({
    theme: 'system',
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
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'offline':
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <div className="h-4 w-4 rounded-full bg-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = "inline-flex items-center gap-1";
    switch (status) {
      case 'online':
        return <Badge className={`${baseClasses} bg-green-100 text-green-800`}>Online</Badge>;
      case 'offline':
        return <Badge className={`${baseClasses} bg-red-100 text-red-800`}>Offline</Badge>;
      case 'error':
        return <Badge className={`${baseClasses} bg-yellow-100 text-yellow-800`}>Error</Badge>;
      default:
        return <Badge className={`${baseClasses} bg-gray-100 text-gray-800`}>Unknown</Badge>;
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
    <div className="container mx-auto p-6 max-w-6xl">
      {/* Navigation Header */}
      <div className="flex items-center gap-3 mb-4">
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={() => navigate('/')}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Workspace
        </Button>
      </div>
      
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600">Manage your account, preferences, and database connections</p>
      </div>

      <Tabs defaultValue="databases" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="databases">
            Databases
          </TabsTrigger>
          <TabsTrigger value="preferences">
            Preferences
          </TabsTrigger>
        </TabsList>

        {/* Database Availability Tab */}
        <TabsContent value="databases" className="space-y-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Database Availability</h2>
                <p className="text-sm text-gray-600">Monitor and manage connections to your enterprise databases</p>
              </div>
              <Button 
                onClick={handleRefreshDatabases} 
                disabled={refreshing}
                variant="outline"
                size="sm"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''} mr-2`} />
                Refresh All
              </Button>
            </div>
            <div>
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
                  <span className="ml-2 text-gray-600">Loading database status...</span>
                </div>
              ) : databaseData ? (
                <div className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-white border p-3 rounded-lg text-center">
                      <p className="text-lg font-semibold text-gray-900">{databaseData.summary.total_databases}</p>
                      <span className="text-xs text-gray-600">Total</span>
                    </div>
                    <div className="bg-white border p-3 rounded-lg text-center">
                      <p className="text-lg font-semibold text-green-600">{databaseData.summary.online}</p>
                      <span className="text-xs text-gray-600">Online</span>
                    </div>
                    <div className="bg-white border p-3 rounded-lg text-center">
                      <p className="text-lg font-semibold text-red-600">{databaseData.summary.offline}</p>
                      <span className="text-xs text-gray-600">Offline</span>
                    </div>
                    <div className="bg-white border p-3 rounded-lg text-center">
                      <p className="text-lg font-semibold text-blue-600">
                        {databaseData.summary.uptime_percentage.toFixed(0)}%
                      </p>
                      <span className="text-xs text-gray-600">Uptime</span>
                    </div>
                  </div>

                  {/* Database List */}
                  <div className="space-y-4">
                    <h3 className="text-base font-medium text-gray-900">Databases</h3>
                    <div className="space-y-2">
                      {databaseData.databases.map((db: DatabaseStatus) => (
                        <div key={db.name} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              {getStatusIcon(db.status)}
                              <div>
                                <h4 className="font-medium text-gray-900 capitalize">{db.name}</h4>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              {getStatusBadge(db.status)}
                              {db.response_time_ms && (
                                <span className="text-sm text-gray-600">
                                  {db.response_time_ms.toFixed(0)}ms
                                </span>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRefreshSingleDatabase(db.name)}
                                className="text-xs"
                              >
                                Test
                              </Button>
                            </div>
                          </div>
                          
                          {db.error_message && (
                            <div className="mt-3 p-2 bg-red-50 rounded text-sm text-red-600">
                              {db.error_message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="h-12 w-12 bg-gray-400 rounded mx-auto mb-4" />
                  <p className="text-gray-600">No database information available</p>
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
                <h3 className="text-sm font-medium text-gray-900">Appearance</h3>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Theme</span>
                  <select 
                    value={preferences.theme}
                    onChange={(e) => updatePreference('theme', e.target.value)}
                    className="border rounded px-3 py-1 text-sm"
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
                <h3 className="text-sm font-medium text-gray-900">Query Behavior</h3>
                
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Auto-save queries</p>
                    <p className="text-xs text-gray-600">Automatically save queries to session history</p>
                  </div>
                  <Switch 
                    checked={preferences.autoSaveQueries}
                    onCheckedChange={(checked) => updatePreference('autoSaveQueries', checked)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Default analyze mode</p>
                    <p className="text-xs text-gray-600">Enable analysis by default for new queries</p>
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
                <h3 className="text-sm font-medium text-gray-900">Live Updates</h3>
                
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Enable notifications</p>
                    <p className="text-xs text-gray-600">Get notified about query completions and alerts</p>
                  </div>
                  <Switch 
                    checked={preferences.enableNotifications}
                    onCheckedChange={(checked) => updatePreference('enableNotifications', checked)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Live database monitoring</p>
                    <p className="text-xs text-gray-600">Automatically refresh database status</p>
                  </div>
                  <Switch 
                    checked={preferences.enableLiveUpdates}
                    onCheckedChange={(checked) => updatePreference('enableLiveUpdates', checked)}
                  />
                </div>

                {preferences.enableLiveUpdates && (
                  <div className="flex items-center justify-between pl-4">
                    <div>
                      <p className="text-sm font-medium">Refresh interval</p>
                      <p className="text-xs text-gray-600">How often to check database status</p>
                    </div>
                    <select 
                      value={preferences.pollInterval}
                      onChange={(e) => updatePreference('pollInterval', parseInt(e.target.value))}
                      className="border rounded px-3 py-1 text-sm"
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
                    <p className="text-sm font-medium">Show advanced settings</p>
                    <p className="text-xs text-gray-600">Display developer and power-user options</p>
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