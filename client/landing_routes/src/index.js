require('dotenv').config();
const express = require('express');
const cors = require('cors');
const waitlistRoutes = require('./routes/waitlistRoutes');
const paymentRoutes = require('./routes/paymentRoutes');
const adminRoutes = require('./routes/adminRoutes');
const blogRoutes = require('./routes/blogRoutes');
// const chatRoutes = require('./routes/chatRoutes'); // Temporarily disabled
const { sequelize } = require('./config/database');

// Redis services and cleanup - temporarily disabled for admin-only functionality
// const cleanupManager = require('./utils/cleanup');
// const redisService = require('./services/redisService');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/waitlist', waitlistRoutes);
app.use('/api/payments', paymentRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/blog', blogRoutes);
// app.use('/api/chat', chatRoutes); // Temporarily disabled

// Health check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// Connect to database and start server
async function startServer() {
  try {
    await sequelize.authenticate();
    console.log('Database connection established successfully.');
    
    // Sync models with database
    await sequelize.sync({ alter: true });
    console.log('Models synchronized with database.');
    
    // Start cleanup tasks - temporarily disabled
    // cleanupManager.start();
    // console.log('Cleanup manager started.');
    
    // Log initial system status - temporarily disabled
    // const redisStatus = redisService.getStatus();
    // console.log('Redis status:', redisStatus);
    
    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
      // console.log('Chat persistence:', redisStatus.connected ? 'Redis' : 'In-memory fallback');
    });
  } catch (error) {
    console.error('Unable to start the server:', error);
  }
}

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('Received SIGINT, shutting down gracefully...');
  
  try {
    cleanupManager.stop();
    await redisService.disconnect();
    await sequelize.close();
    console.log('Server shutdown complete');
    process.exit(0);
  } catch (error) {
    console.error('Error during shutdown:', error);
    process.exit(1);
  }
});

process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, shutting down gracefully...');
  
  try {
    cleanupManager.stop();
    await redisService.disconnect();
    await sequelize.close();
    console.log('Server shutdown complete');
    process.exit(0);
  } catch (error) {
    console.error('Error during shutdown:', error);
    process.exit(1);
  }
});

startServer(); 