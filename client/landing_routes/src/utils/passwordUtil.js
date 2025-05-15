const bcrypt = require('bcryptjs');

/**
 * Utility to generate a bcrypt hash for a password
 * Usage: node passwordUtil.js [password]
 */
const generateHash = async (password) => {
  try {
    // Generate a salt with 10 rounds
    const salt = await bcrypt.genSalt(10);
    
    // Hash the password with the salt
    const hash = await bcrypt.hash(password, salt);
    
    console.log(`Password: ${password}`);
    console.log(`Hash: ${hash}`);
    
    // Verify the hash
    const isValid = await bcrypt.compare(password, hash);
    console.log(`Verification: ${isValid ? 'Valid' : 'Invalid'}`);
    
    return hash;
  } catch (error) {
    console.error('Error generating hash:', error);
    throw error;
  }
};

// Execute if called directly
if (require.main === module) {
  const password = process.argv[2] || 'adminPassword';
  
  generateHash(password)
    .then(() => {
      console.log('Hash generation complete');
    })
    .catch((err) => {
      console.error('Hash generation failed:', err);
    });
}

module.exports = {
  generateHash
}; 