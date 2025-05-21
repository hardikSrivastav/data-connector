const User = require('../models/User');
const Waitlist = require('../models/Waitlist');
const { sequelize } = require('../config/database');
const emailService = require('../utils/emailService');

/**
 * Register a new user for the waitlist
 */
exports.register = async (req, res) => {
  const { name, email, company } = req.body;
  
  // Start a transaction
  const transaction = await sequelize.transaction();
  
  try {
    // Check if user already exists
    const existingUser = await User.findOne({ where: { email } });
    if (existingUser) {
      await transaction.rollback();
      return res.status(400).json({ 
        success: false, 
        message: 'Email already registered for the waitlist' 
      });
    }
    
    // Create user
    const user = await User.create({
      name,
      email,
      company
    }, { transaction });
    
    // Get the current max position in the waitlist
    const maxPositionResult = await Waitlist.findOne({
      attributes: [[sequelize.fn('max', sequelize.col('position')), 'maxPosition']],
      raw: true
    });
    
    const currentMaxPosition = maxPositionResult.maxPosition || 0;
    
    // Create waitlist entry
    const waitlistEntry = await Waitlist.create({
      userId: user.id,
      position: currentMaxPosition + 1,
      status: 'pending'
    }, { transaction });
    
    await transaction.commit();
    
    // Send emails after successful registration
    try {
      // Send thank you email to user
      await emailService.sendThankYouEmail({
        name,
        email,
        company
      });
      
      // Send notification email to admin
      await emailService.sendAdminNotificationEmail(
        {
          name,
          email,
          company
        },
        waitlistEntry.position
      );
    } catch (emailError) {
      // Log the error but don't fail the registration process
      console.error('Error sending emails:', emailError);
    }
    
    return res.status(201).json({
      success: true,
      data: {
        userId: user.id,
        waitlistId: waitlistEntry.id,
        position: waitlistEntry.position
      }
    });
  } catch (error) {
    await transaction.rollback();
    console.error('Error registering for waitlist:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to register for waitlist',
      error: error.message
    });
  }
};

/**
 * Get waitlist status for a user
 */
exports.getStatus = async (req, res) => {
  const { userId } = req.params;
  
  try {
    const waitlistEntry = await Waitlist.findOne({
      where: { userId },
      include: [{ model: User, attributes: ['name', 'email', 'company'] }]
    });
    
    if (!waitlistEntry) {
      return res.status(404).json({
        success: false,
        message: 'User not found in waitlist'
      });
    }
    
    return res.status(200).json({
      success: true,
      data: {
        userId: waitlistEntry.userId,
        position: waitlistEntry.position,
        status: waitlistEntry.status,
        user: waitlistEntry.User
      }
    });
  } catch (error) {
    console.error('Error fetching waitlist status:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to fetch waitlist status',
      error: error.message
    });
  }
};

/**
 * Check waitlist status by email
 */
exports.checkStatusByEmail = async (req, res) => {
  const { email } = req.body;
  
  if (!email) {
    return res.status(400).json({
      success: false,
      message: 'Email is required'
    });
  }

  try {
    // Find user by email
    const user = await User.findOne({ where: { email } });
    
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found with this email'
      });
    }
    
    // Find waitlist entry for this user
    const waitlistEntry = await Waitlist.findOne({
      where: { userId: user.id }
    });
    
    if (!waitlistEntry) {
      return res.status(404).json({
        success: false,
        message: 'User not found in waitlist'
      });
    }
    
    return res.status(200).json({
      success: true,
      data: {
        userId: waitlistEntry.userId,
        position: waitlistEntry.position,
        status: waitlistEntry.status,
        user: {
          name: user.name,
          email: user.email,
          company: user.company
        }
      }
    });
  } catch (error) {
    console.error('Error checking waitlist status by email:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to check waitlist status',
      error: error.message
    });
  }
}; 