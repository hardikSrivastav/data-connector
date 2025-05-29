import { useState, useEffect, useCallback } from 'react';
import { Page, Block, Workspace } from '@/types';
import { EnterpriseStorageConfig, SyncState, Change } from '@/types/storage';
import { SyncStrategy, EnterpriseSyncStrategy, ZeroSyncStrategy } from './sync-strategies';

export class StorageManager {
  private db: IDBDatabase | null = null;
  private cache = new Map<string, any>();
  private config: EnterpriseStorageConfig;
  private syncState: SyncState;
  private syncStrategy: SyncStrategy;

  constructor(config: EnterpriseStorageConfig) {
    this.config = config;
    this.syncState = {
      isOnline: navigator.onLine,
      lastSync: null,
      pendingChanges: [],
      conflictResolution: 'merge'
    };
    
    // Strategy selection based on edition
    this.syncStrategy = config.edition === 'zero-sync' 
      ? new ZeroSyncStrategy()
      : new EnterpriseSyncStrategy(config);
    
    this.initializeDB();
    this.setupEventListeners();
  }

  // IndexedDB initialization
  private async initializeDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('NotionCloneDB', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        // Create object stores
        if (!db.objectStoreNames.contains('workspaces')) {
          db.createObjectStore('workspaces', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('pages')) {
          const pageStore = db.createObjectStore('pages', { keyPath: 'id' });
          pageStore.createIndex('workspaceId', 'workspaceId', { unique: false });
        }
        if (!db.objectStoreNames.contains('blocks')) {
          const blockStore = db.createObjectStore('blocks', { keyPath: 'id' });
          blockStore.createIndex('pageId', 'pageId', { unique: false });
        }
        if (!db.objectStoreNames.contains('changes')) {
          const changeStore = db.createObjectStore('changes', { keyPath: 'id' });
          changeStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
    });
  }

  // Event listeners for online/offline detection
  private setupEventListeners(): void {
    window.addEventListener('online', () => {
      this.syncState.isOnline = true;
      this.syncPendingChanges();
    });
    
    window.addEventListener('offline', () => {
      this.syncState.isOnline = false;
    });
  }

  // Memory cache operations
  private getCached<T>(key: string): T | null {
    const cached = this.cache.get(key);
    if (cached && cached.expiry > Date.now()) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  private setCache<T>(key: string, data: T, ttl: number = 300000): void {
    this.cache.set(key, {
      data,
      expiry: Date.now() + ttl
    });
  }

  // IndexedDB operations
  private async getFromDB<T>(store: string, key: string): Promise<T | null> {
    if (!this.db) return null;
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([store], 'readonly');
      const objectStore = transaction.objectStore(store);
      const request = objectStore.get(key);
      
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  }

  private async saveTooDB<T>(store: string, data: T): Promise<void> {
    if (!this.db) return;
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([store], 'readwrite');
      const objectStore = transaction.objectStore(store);
      const request = objectStore.put(data);
      
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  // API operations using strategy pattern
  private async syncToServer<T>(endpoint: string, data: T): Promise<T> {
    // Validate data first (different rules per edition)
    this.syncStrategy.validateData(data);
    
    // Use strategy for sync
    return this.syncStrategy.syncToServer(endpoint, data);
  }

  private async fetchFromServer<T>(endpoint: string): Promise<T> {
    return this.syncStrategy.fetchFromServer(endpoint);
  }

  // Public API
  async getWorkspace(id: string): Promise<Workspace | null> {
    // 1. Check memory cache
    const cached = this.getCached<Workspace>(`workspace:${id}`);
    if (cached) return cached;

    // 2. Check IndexedDB
    const local = await this.getFromDB<Workspace>('workspaces', id);
    if (local) {
      this.setCache(`workspace:${id}`, local);
      return local;
    }

    // 3. Fetch from server if online and not zero-sync
    if (this.syncState.isOnline && this.config.edition !== 'zero-sync') {
      try {
        const remote = await this.fetchFromServer<Workspace>(`workspaces/${id}`);
        await this.saveTooDB('workspaces', remote);
        this.setCache(`workspace:${id}`, remote);
        return remote;
      } catch (error) {
        console.error('Failed to fetch workspace from server:', error);
      }
    }

    return null;
  }

  async saveWorkspace(workspace: Workspace): Promise<Workspace> {
    // Optimistic update
    this.setCache(`workspace:${workspace.id}`, workspace);
    
    // Save to IndexedDB
    await this.saveTooDB('workspaces', workspace);
    
    // Also save individual pages for better sync granularity
    await Promise.all(
      workspace.pages.map(page => this.savePage(page))
    );
    
    // Different behavior per edition
    if (this.config.edition === 'enterprise') {
      // Queue for server sync
      const change: Change = {
        id: `${Date.now()}-${Math.random()}`,
        type: 'update',
        entity: 'workspace',
        entityId: workspace.id,
        data: workspace,
        timestamp: new Date(),
        userId: 'current-user' // Get from auth context
      };
      
      this.syncState.pendingChanges.push(change);
      await this.saveTooDB('changes', change);
      
      // Sync immediately if online
      if (this.syncState.isOnline) {
        this.syncPendingChanges();
      }
    }
    // Zero-sync: no server sync, just local storage
    
    return workspace;
  }

  async savePage(page: Page): Promise<Page> {
    // Optimistic update
    this.setCache(`page:${page.id}`, page);
    
    // Save to IndexedDB
    await this.saveTooDB('pages', page);
    
    // Different behavior per edition
    if (this.config.edition === 'enterprise') {
      // Queue for server sync
      const change: Change = {
        id: `${Date.now()}-${Math.random()}`,
        type: 'update',
        entity: 'page',
        entityId: page.id,
        data: page,
        timestamp: new Date(),
        userId: 'current-user' // Get from auth context
      };
      
      this.syncState.pendingChanges.push(change);
      await this.saveTooDB('changes', change);
      
      // Sync immediately if online
      if (this.syncState.isOnline) {
        this.syncPendingChanges();
      }
    }
    // Zero-sync: no server sync, just local storage
    
    return page;
  }

  async saveBlock(block: Block, pageId: string): Promise<Block> {
    // Enhanced block with metadata
    const enhancedBlock = {
      ...block,
      pageId,
      updatedAt: new Date()
    };
    
    // Same pattern as savePage
    this.setCache(`block:${block.id}`, enhancedBlock);
    await this.saveTooDB('blocks', enhancedBlock);
    
    // Different behavior per edition
    if (this.config.edition === 'enterprise') {
      const change: Change = {
        id: `${Date.now()}-${Math.random()}`,
        type: 'update',
        entity: 'block',
        entityId: block.id,
        data: enhancedBlock,
        timestamp: new Date(),
        userId: 'current-user'
      };
      
      this.syncState.pendingChanges.push(change);
      await this.saveTooDB('changes', change);
      
      if (this.syncState.isOnline) {
        this.syncPendingChanges();
      }
    }
    
    return enhancedBlock;
  }

  async deleteBlock(blockId: string): Promise<void> {
    // Remove from cache
    this.cache.delete(`block:${blockId}`);
    
    // Remove from IndexedDB
    if (this.db) {
      const transaction = this.db.transaction(['blocks'], 'readwrite');
      const objectStore = transaction.objectStore('blocks');
      await objectStore.delete(blockId);
    }
    
    // Different behavior per edition
    if (this.config.edition === 'enterprise') {
      const change: Change = {
        id: `${Date.now()}-${Math.random()}`,
        type: 'delete',
        entity: 'block',
        entityId: blockId,
        data: null,
        timestamp: new Date(),
        userId: 'current-user'
      };
      
      this.syncState.pendingChanges.push(change);
      await this.saveTooDB('changes', change);
      
      if (this.syncState.isOnline) {
        this.syncPendingChanges();
      }
    }
  }

  private async syncPendingChanges(): Promise<void> {
    if (!this.syncState.isOnline || this.syncState.pendingChanges.length === 0 || this.config.edition === 'zero-sync') {
      return;
    }

    try {
      // Send changes to server
      const response = await this.syncToServer('sync', {
        changes: this.syncState.pendingChanges,
        lastSync: this.syncState.lastSync
      });

      // Handle server response and conflicts
      if (response.changes && response.changes.length > 0) {
        await this.resolveConflicts(response.changes);
      }

      // Clear synced changes
      this.syncState.pendingChanges = [];
      this.syncState.lastSync = new Date();
      
      // Clear changes from IndexedDB
      await this.clearSyncedChanges();
      
    } catch (error) {
      console.error('Sync failed:', error);
    }
  }

  private async resolveConflicts(conflicts: any[]): Promise<void> {
    // Implement conflict resolution based on strategy
    for (const conflict of conflicts) {
      switch (this.syncState.conflictResolution) {
        case 'server':
          // Accept server version
          await this.saveTooDB(conflict.entity + 's', conflict.serverData);
          break;
        case 'client':
          // Keep client version, re-queue for sync
          break;
        case 'merge':
          // Implement merge logic
          const merged = this.mergeData(conflict.clientData, conflict.serverData);
          await this.saveTooDB(conflict.entity + 's', merged);
          break;
      }
    }
  }

  private mergeData(client: any, server: any): any {
    // Simple merge strategy - can be enhanced
    return {
      ...server,
      ...client,
      updatedAt: new Date()
    };
  }

  private async clearSyncedChanges(): Promise<void> {
    if (!this.db) return;
    
    const transaction = this.db.transaction(['changes'], 'readwrite');
    const objectStore = transaction.objectStore('changes');
    await objectStore.clear();
  }

  // Utility methods
  async clearCache(): Promise<void> {
    this.cache.clear();
  }

  async getStorageStats(): Promise<{
    indexedDBSize: number;
    cacheSize: number;
    pendingChanges: number;
  }> {
    return {
      indexedDBSize: 0, // Calculate actual size
      cacheSize: this.cache.size,
      pendingChanges: this.syncState.pendingChanges.length
    };
  }
}

export const useStorageManager = (config?: Partial<EnterpriseStorageConfig>) => {
  const [storageManager] = useState(() => new StorageManager({
    edition: 'enterprise', // Default to enterprise
    enableOffline: true,
    syncInterval: 30000, // 30 seconds
    autoSaveInterval: 5000, // 5 seconds
    maxCacheSize: 100,
    ...config
  }));

  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'error'>('idle');

  useEffect(() => {
    const handleOnlineStatus = () => setIsOnline(navigator.onLine);
    
    window.addEventListener('online', handleOnlineStatus);
    window.addEventListener('offline', handleOnlineStatus);
    
    return () => {
      window.removeEventListener('online', handleOnlineStatus);
      window.removeEventListener('offline', handleOnlineStatus);
    };
  }, []);

  return {
    storageManager,
    isOnline,
    syncStatus,
    // Convenience methods
    getWorkspace: useCallback((id: string) => storageManager.getWorkspace(id), [storageManager]),
    saveWorkspace: useCallback((workspace: Workspace) => storageManager.saveWorkspace(workspace), [storageManager]),
    savePage: useCallback((page: Page) => storageManager.savePage(page), [storageManager]),
    saveBlock: useCallback((block: Block, pageId: string) => storageManager.saveBlock(block, pageId), [storageManager]),
    deleteBlock: useCallback((blockId: string) => storageManager.deleteBlock(blockId), [storageManager]),
    clearCache: useCallback(() => storageManager.clearCache(), [storageManager]),
  };
}; 