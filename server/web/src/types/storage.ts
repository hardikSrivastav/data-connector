export interface StorageConfig {
  enableOffline: boolean;
  syncInterval: number;
  autoSaveInterval: number;
  maxCacheSize: number;
}

export interface EnterpriseStorageConfig extends StorageConfig {
  edition: 'enterprise' | 'zero-sync';
  apiBaseUrl?: string;  // Points to enterprise API for 'enterprise' edition
  security?: {
    validateExternalRefs: boolean;
    encryptLocalStorage: boolean;
    auditLevel: 'basic' | 'enhanced' | 'maximum';
  };
}

export interface SyncState {
  isOnline: boolean;
  lastSync: Date | null;
  pendingChanges: Change[];
  conflictResolution: 'client' | 'server' | 'merge';
}

export interface Change {
  id: string;
  type: 'create' | 'update' | 'delete';
  entity: 'workspace' | 'page' | 'block';
  entityId: string;
  data: any;
  timestamp: Date;
  userId: string;
} 