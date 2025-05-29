import { EnterpriseStorageConfig } from '@/types/storage';
import { StorageManager } from './useStorageManager';

// Export edition-specific configurations
export const useEnterpriseStorageManager = (apiBaseUrl?: string) => {
  const config: EnterpriseStorageConfig = {
    edition: 'enterprise',
    apiBaseUrl: apiBaseUrl || import.meta.env.VITE_API_BASE || 'http://localhost:8787',
    enableOffline: true,
    syncInterval: 30000,
    autoSaveInterval: 5000,
    maxCacheSize: 100,
    security: {
      validateExternalRefs: false,
      encryptLocalStorage: true,
      auditLevel: 'enhanced'
    }
  };
  
  return new StorageManager(config);
};

export const useZeroSyncStorageManager = () => {
  const config: EnterpriseStorageConfig = {
    edition: 'zero-sync',
    enableOffline: true,
    syncInterval: 0,        // No sync
    autoSaveInterval: 1000, // Save more frequently locally
    maxCacheSize: 200,      // Larger cache since no server
    security: {
      validateExternalRefs: true,   // Strict validation
      encryptLocalStorage: true,
      auditLevel: 'maximum'
    }
  };
  
  return new StorageManager(config);
};

// Environment-aware hook that automatically selects the right edition
export const useStorageManagerByEnvironment = () => {
  const isZeroSync = import.meta.env.VITE_EDITION === 'zero-sync';
  
  return isZeroSync 
    ? useZeroSyncStorageManager()
    : useEnterpriseStorageManager();
};

// Re-export the base hook for backward compatibility
export { useStorageManager } from './useStorageManager'; 