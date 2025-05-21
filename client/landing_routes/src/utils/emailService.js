const nodemailer = require('nodemailer');

// Configure nodemailer transporter
const transporter = nodemailer.createTransport({
  service: process.env.EMAIL_SERVICE || 'gmail',
  auth: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_PASSWORD
  }
});

/**
 * Send a thank you email to a user who joined the waitlist
 * @param {Object} user - User information
 * @param {string} user.name - User name
 * @param {string} user.email - User email
 * @param {string} user.company - User company
 */
exports.sendThankYouEmail = async (user) => {
  try {
    const mailOptions = {
      from: process.env.EMAIL_USER,
      to: user.email,
      subject: 'Welcome to the Ceneca Waitlist!',
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2>Thank you for joining our waitlist, ${user.name}!</h2>
          <p>We're thrilled to have you on board. Ceneca is working hard to revolutionize data querying, and we can't wait to share our progress with you.</p>
          <p>We'll be sending regular updates about our development and will notify you as soon as early access is available.</p>
          <p>If you have any questions or feedback in the meantime, feel free to reach out to us directly at <a href="mailto:hardik@ceneca.ai">hardik@ceneca.ai</a>.</p>
          <p>Thank you again for your interest and support!</p>
          <p>Best regards,<br>The Ceneca Team</p>
        </div>
      `
    };

    await transporter.sendMail(mailOptions);
    console.log(`Thank you email sent to ${user.email}`);
    return true;
  } catch (error) {
    console.error('Error sending thank you email:', error);
    return false;
  }
};

/**
 * Send a notification email to admin when a new user joins the waitlist
 * @param {Object} user - User information
 * @param {string} user.name - User name
 * @param {string} user.email - User email
 * @param {string} user.company - User company
 * @param {number} position - User's position in the waitlist
 */
exports.sendAdminNotificationEmail = async (user, position) => {
  try {
    const adminEmails = ['hardik@ceneca.ai', 'hardik.srivastava2007@gmail.com'];
    
    const mailOptions = {
      from: process.env.EMAIL_USER,
      to: adminEmails.join(','),
      subject: 'New Waitlist Signup: ' + user.name,
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2>New Waitlist Signup</h2>
          <p>A new user has joined the Ceneca waitlist:</p>
          <ul>
            <li><strong>Name:</strong> ${user.name}</li>
            <li><strong>Email:</strong> ${user.email}</li>
            <li><strong>Company:</strong> ${user.company || 'Not provided'}</li>
            <li><strong>Waitlist Position:</strong> ${position}</li>
          </ul>
        </div>
      `
    };

    await transporter.sendMail(mailOptions);
    console.log(`Admin notification email sent for ${user.email}`);
    return true;
  } catch (error) {
    console.error('Error sending admin notification email:', error);
    return false;
  }
}; 