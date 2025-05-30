import { EnterpriseStorageConfig } from '@/types/storage';

// Strategy pattern for different sync behaviors
export interface SyncStrategy {
  syncToServer<T>(endpoint: string, data: T): Promise<T>;
  fetchFromServer<T>(endpoint: string): Promise<T>;
  validateData(data: any): void;
}

export class EnterpriseSyncStrategy implements SyncStrategy {
  constructor(private config: EnterpriseStorageConfig) {}
  
  async syncToServer<T>(endpoint: string, data: T): Promise<T> {
    // Sync to enterprise on-premise API
    const url = `${this.config.apiBaseUrl}/api/${endpoint}`;
    console.log('🔄 Syncing to server:', url);
    console.log('📤 Sync data:', data);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.getAuthToken()}`
      },
      body: JSON.stringify(data)
    });
    
    console.log('📥 Sync response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Sync failed:', response.status, errorText);
      throw new Error(`Enterprise sync failed: ${response.status} - ${errorText}`);
    }
    
    const result = await response.json();
    console.log('✅ Sync successful:', result);
    return result;
  }
  
  async fetchFromServer<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.config.apiBaseUrl}/api/${endpoint}`, {
      headers: {
        'Authorization': `Bearer ${this.getAuthToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`Enterprise fetch failed: ${response.status}`);
    }
    
    return response.json();
  }
  
  validateData(data: any): void {
    // Basic validation for enterprise edition
    if (this.config.security?.auditLevel === 'enhanced' || this.config.security?.auditLevel === 'maximum') {
      this.logDataAccess(data);
    }
  }
  
  private getAuthToken(): string {
    // Get JWT token from enterprise SSO context
    return localStorage.getItem('enterprise_token') || '';
  }
  
  private logDataAccess(data: any): void {
    // Audit logging for enterprise compliance
    const auditEntry = {
      timestamp: new Date(),
      action: 'data_sync',
      dataType: data.entity || 'unknown',
      userId: localStorage.getItem('user_id'),
    };
    
    // Send to audit endpoint (non-blocking)
    this.sendAuditLog(auditEntry).catch(console.warn);
  }
  
  private async sendAuditLog(auditEntry: any): Promise<void> {
    try {
      await fetch(`${this.config.apiBaseUrl}/api/audit`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify(auditEntry)
      });
    } catch (error) {
      console.warn('Audit logging failed:', error);
    }
  }
}

export class ZeroSyncStrategy implements SyncStrategy {
  async syncToServer<T>(endpoint: string, data: T): Promise<T> {
    // No-op: zero sync mode
    console.log('Sync disabled in zero-sync mode');
    return data;
  }
  
  async fetchFromServer<T>(endpoint: string): Promise<T> {
    throw new Error('External fetch disabled in zero-sync mode');
  }
  
  validateData(data: any): void {
    // Strict validation: no external references allowed
    const dataString = JSON.stringify(data);
    const externalPatterns = [
      /https?:\/\/(?![\w-]+\.internal)/i,  // No external URLs
      /api\.(openai|anthropic)\.com/i,     // No AI service refs
      /\.amazonaws\.com/i,                 // No cloud service refs
      /\.googleapis\.com/i,                // No Google service refs
    ];
    
    externalPatterns.forEach(pattern => {
      if (pattern.test(dataString)) {
        throw new Error('External reference detected in zero-sync mode');
      }
    });
    
    // Log locally for audit trail
    this.logLocalAudit(data);
  }
  
  private logLocalAudit(data: any): void {
    const auditEntry = {
      timestamp: new Date(),
      action: 'data_access',
      dataType: data.entity || 'unknown',
      userId: localStorage.getItem('user_id'),
    };
    
    // Store in local audit log (IndexedDB)
    const auditLog = JSON.parse(localStorage.getItem('ceneca_audit_log') || '[]');
    auditLog.push(auditEntry);
    
    // Keep only last 1000 entries for performance
    if (auditLog.length > 1000) {
      auditLog.splice(0, auditLog.length - 1000);
    }
    
    localStorage.setItem('ceneca_audit_log', JSON.stringify(auditLog));
  }
} 