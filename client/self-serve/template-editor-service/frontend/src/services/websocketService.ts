const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8501';

export class WebSocketService {
  private socket: WebSocket | null = null;
  private sessionId: string | null = null;
  private messageHandlers: Array<(message: string) => void> = [];
  private connectionHandlers: Array<(connected: boolean) => void> = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId;
    
    return new Promise((resolve, reject) => {
      try {
        // Use relative URL in production, absolute in development
        const wsUrl = window.location.protocol === 'https:' 
          ? `wss://${window.location.host}/ws/${sessionId}`
          : `ws://${window.location.host}/ws/${sessionId}`;
        
        console.log('Connecting to WebSocket URL:', wsUrl);
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          console.log('WebSocket connected to session:', sessionId);
          this.reconnectAttempts = 0;
          // Use setTimeout to ensure connection handlers are set up
          setTimeout(() => {
            this.notifyConnectionHandlers(true);
          }, 50);
          resolve();
        };

        this.socket.onmessage = (event) => {
          const message = event.data;
          console.log('WebSocket message received:', message);
          this.notifyMessageHandlers(message);
        };

        this.socket.onclose = (event) => {
          console.log('WebSocket connection closed:', event.code, event.reason);
          this.notifyConnectionHandlers(false);
          
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };

        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };

      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        reject(error);
      }
    });
  }

  private attemptReconnect(): void {
    if (!this.sessionId) return;

    this.reconnectAttempts++;
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect(this.sessionId!).catch(() => {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          console.error('Max reconnection attempts reached');
        }
      });
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  sendMessage(message: string): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(message);
      console.log('WebSocket message sent:', message);
    } else {
      console.error('WebSocket is not connected');
      throw new Error('WebSocket connection not available');
    }
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.close(1000, 'User disconnected');
      this.socket = null;
    }
    this.sessionId = null;
    this.messageHandlers = [];
    this.connectionHandlers = [];
  }

  onMessage(handler: (message: string) => void): void {
    this.messageHandlers.push(handler);
  }

  onConnection(handler: (connected: boolean) => void): void {
    this.connectionHandlers.push(handler);
  }

  removeMessageHandler(handler: (message: string) => void): void {
    this.messageHandlers = this.messageHandlers.filter(h => h !== handler);
  }

  removeConnectionHandler(handler: (connected: boolean) => void): void {
    this.connectionHandlers = this.connectionHandlers.filter(h => h !== handler);
  }

  private notifyMessageHandlers(message: string): void {
    this.messageHandlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error('Error in message handler:', error);
      }
    });
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(connected);
      } catch (error) {
        console.error('Error in connection handler:', error);
      }
    });
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  // Get current connection status and trigger handlers if needed
  checkConnectionStatus(): void {
    const connected = this.isConnected();
    console.log('Checking connection status:', connected);
    this.notifyConnectionHandlers(connected);
  }
}

export const websocketService = new WebSocketService();