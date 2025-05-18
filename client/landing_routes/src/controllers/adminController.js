const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const User = require('../models/User');
const Payment = require('../models/Payment');
const Waitlist = require('../models/Waitlist');
const { sequelize } = require('../config/database');

// Admin users (in production, this would be in a database)
const ADMIN_USERS = {
  'admin@ceneca.ai': {
    plainPassword: 'adminPassword', // Plain text for direct comparison
    name: 'Admin User'
  }
};

// Secret key for JWT
const JWT_SECRET = process.env.JWT_SECRET || 'admin-secret-key-change-in-production';

/**
 * Admin login
 */
exports.login = async (req, res) => {
  const { email, password } = req.body;
  
  console.log('================================');
  console.log('Login attempt:', { email, providedPassword: password ? password : 'empty' });
  console.log('Password type:', typeof password);
  console.log('Password length:', password ? password.length : 0);

  try {
    // Check if email exists
    const adminUser = ADMIN_USERS[email];
    console.log('Admin user found:', adminUser ? 'Yes' : 'No');
    
    if (!adminUser) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials'
      });
    }

    // Log expected password
    console.log('Expected password:', adminUser.plainPassword);
    console.log('Expected password type:', typeof adminUser.plainPassword);
    console.log('Expected password length:', adminUser.plainPassword.length);
    
    // Check for exact character-by-character equality
    let charMismatch = false;
    for (let i = 0; i < Math.max(password.length, adminUser.plainPassword.length); i++) {
      if (password[i] !== adminUser.plainPassword[i]) {
        console.log(`Mismatch at position ${i}: expected '${adminUser.plainPassword[i]}', got '${password[i]}'`);
        charMismatch = true;
      }
    }
    
    // Direct string comparison for simplicity
    console.log('Using direct string comparison for password');
    const isMatch = password === adminUser.plainPassword;
    console.log('Password match:', isMatch);
    console.log('JSON.stringify check:', JSON.stringify(password) === JSON.stringify(adminUser.plainPassword));
    console.log('================================');
    
    if (!isMatch) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials'
      });
    }

    // Create token
    const token = jwt.sign(
      { email, name: adminUser.name },
      JWT_SECRET,
      { expiresIn: '8h' }
    );

    return res.status(200).json({
      success: true,
      data: {
        token,
        name: adminUser.name,
        email
      }
    });
  } catch (error) {
    console.error('Error during admin login:', error);
    return res.status(500).json({
      success: false,
      message: 'Login failed',
      error: error.message
    });
  }
};

/**
 * Get all waitlist entries with users and payment info
 */
exports.getWaitlist = async (req, res) => {
  try {
    const waitlistEntries = await Waitlist.findAll({
      include: [
        { model: User, attributes: ['id', 'name', 'email', 'company', 'createdAt'] }
      ],
      order: [['position', 'ASC']]
    });

    // Get payment info for each user
    const userIds = waitlistEntries.map(entry => entry.userId);
    const payments = await Payment.findAll({
      where: { userId: userIds },
      attributes: ['userId', 'status', 'amount', 'paymentDate']
    });

    // Map payments to waitlist entries
    const waitlistWithPayments = waitlistEntries.map(entry => {
      const userPayment = payments.find(payment => payment.userId === entry.userId);
      return {
        id: entry.id,
        position: entry.position,
        status: entry.status,
        notes: entry.notes,
        createdAt: entry.createdAt,
        user: entry.User,
        payment: userPayment || null
      };
    });

    return res.status(200).json({
      success: true,
      data: waitlistWithPayments
    });
  } catch (error) {
    console.error('Error fetching waitlist:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to fetch waitlist',
      error: error.message
    });
  }
};

/**
 * Update waitlist entry position or status
 */
exports.updateWaitlist = async (req, res) => {
  const { id } = req.params;
  const { position, status, notes } = req.body;
  const transaction = await sequelize.transaction();

  try {
    const waitlistEntry = await Waitlist.findByPk(id);
    if (!waitlistEntry) {
      await transaction.rollback();
      return res.status(404).json({
        success: false,
        message: 'Waitlist entry not found'
      });
    }

    // If changing position, make sure it's valid
    if (position !== undefined) {
      if (position < 1) {
        await transaction.rollback();
        return res.status(400).json({
          success: false,
          message: 'Position must be a positive integer'
        });
      }

      // If position is decreasing (moving up in waitlist)
      if (position < waitlistEntry.position) {
        // Increment position of entries that will now be below this one
        await Waitlist.increment('position', {
          by: 1,
          where: {
            position: {
              [sequelize.Op.gte]: position,
              [sequelize.Op.lt]: waitlistEntry.position
            }
          },
          transaction
        });
      } 
      // If position is increasing (moving down in waitlist)
      else if (position > waitlistEntry.position) {
        // Decrement position of entries that will now be above this one
        await Waitlist.decrement('position', {
          by: 1,
          where: {
            position: {
              [sequelize.Op.gt]: waitlistEntry.position,
              [sequelize.Op.lte]: position
            }
          },
          transaction
        });
      }
    }

    // Update the waitlist entry
    await waitlistEntry.update({
      position: position !== undefined ? position : waitlistEntry.position,
      status: status !== undefined ? status : waitlistEntry.status,
      notes: notes !== undefined ? notes : waitlistEntry.notes
    }, { transaction });

    await transaction.commit();

    return res.status(200).json({
      success: true,
      data: {
        id: waitlistEntry.id,
        position: waitlistEntry.position,
        status: waitlistEntry.status,
        notes: waitlistEntry.notes
      }
    });
  } catch (error) {
    await transaction.rollback();
    console.error('Error updating waitlist entry:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to update waitlist entry',
      error: error.message
    });
  }
}; 