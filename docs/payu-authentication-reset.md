# PayU Authentication Reset

This document explains how to reset PayU authentication in the Ceneca data connector.

## Overview

The PayU adapter stores authentication credentials in a local file (`~/.data-connector/payu_credentials.json`). If you need to reset these credentials (e.g., due to credential changes, security concerns, or troubleshooting), you can use the reset functionality.

## Reset Methods

### Method 1: CLI Command (Recommended)

Use the new `reset_auth` command:

```bash
# Reset with confirmation prompt
python -m agent.cmd.query reset_auth payu

# Reset without confirmation (force)
python -m agent.cmd.query reset_auth payu --force
```

### Method 2: Programmatic Reset

You can also reset authentication programmatically:

```python
from agent.db.adapters.payu import PayUAdapter

# Create adapter
adapter = PayUAdapter("https://test.payu.in")

# Reset authentication
success = adapter.reset_authentication()

if success:
    print("Authentication reset successful!")
else:
    print("Authentication reset failed!")
```

## What Gets Reset

The reset process:

1. **Clears in-memory credentials** - Removes stored credentials from the adapter instance
2. **Removes credentials file** - Deletes `~/.data-connector/payu_credentials.json`
3. **Closes active sessions** - Terminates any active HTTP sessions
4. **Resets auth config** - Clears the internal authentication configuration

## After Reset

Once authentication is reset:

1. **No stored credentials** - The adapter will not have access to previous credentials
2. **Fresh authentication required** - You'll need to re-authenticate before making API calls
3. **Clean slate** - All previous authentication state is cleared

## Re-authentication

After resetting, you can re-authenticate using:

```bash
# Interactive authentication
python -m agent.cmd.query authenticate payu

# With command line parameters
python -m agent.cmd.query authenticate payu \
  --merchant-key "your_merchant_key" \
  --salt "your_salt" \
  --merchant-id "your_merchant_id" \
  --environment "test"
```

## Verification

To verify the reset worked:

1. Check that the credentials file is removed:
   ```bash
   ls -la ~/.data-connector/payu_credentials.json
   ```

2. Try to authenticate again - it should prompt for credentials

3. Test connection after re-authentication:
   ```bash
   python -m agent.cmd.query test_connection --type payu
   ```

## Troubleshooting

### Reset Fails

If the reset fails:

1. **Check file permissions** - Ensure you have write access to `~/.data-connector/`
2. **Manual cleanup** - Manually delete the credentials file if needed
3. **Check for active sessions** - Ensure no other processes are using the adapter

### Re-authentication Fails

If re-authentication fails after reset:

1. **Verify credentials** - Double-check your PayU merchant key, salt, and merchant ID
2. **Check environment** - Ensure you're using the correct environment (test/production)
3. **Network connectivity** - Verify you can reach the PayU API endpoints

## Security Notes

- The reset process permanently removes stored credentials
- No credentials are logged or stored in plain text during the reset process
- The reset is irreversible - you must re-authenticate to use the adapter again
- Consider resetting authentication if you suspect credentials have been compromised

## Other Database Types

The reset functionality is also available for other database types:

```bash
# Reset Shopify authentication
python -m agent.cmd.query reset_auth shopify

# Reset Slack authentication  
python -m agent.cmd.query reset_auth slack

# Reset Shiprocket authentication
python -m agent.cmd.query reset_auth shiprocket

# Reset Easebuzz authentication
python -m agent.cmd.query reset_auth easebuzz
``` 