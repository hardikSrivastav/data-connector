# SSL Certificates

This directory should contain your SSL certificates for HTTPS.

## Required Files

- `certificate.crt` - Your SSL certificate
- `private.key` - Your private key

## Setup Options

### Option 1: Use Your Organization's SSL Certificate

```bash
# Copy your certificate files here
cp /path/to/your/certificate.crt certs/
cp /path/to/your/private.key certs/

# Ensure proper permissions
chmod 600 certs/private.key
chmod 644 certs/certificate.crt
```

### Option 2: Generate Self-Signed Certificate (Testing Only)

```bash
# Generate for your domain
../scripts/generate-self-signed.sh ceneca.yourcompany.com

# Or for localhost testing
../scripts/generate-self-signed.sh localhost
```

### Option 3: Use Let's Encrypt (Manual Setup)

```bash
# Install certbot first
sudo apt install certbot  # Ubuntu/Debian
brew install certbot      # macOS

# Generate certificate
sudo certbot certonly --standalone -d ceneca.yourcompany.com

# Copy to this directory
sudo cp /etc/letsencrypt/live/ceneca.yourcompany.com/fullchain.pem certs/certificate.crt
sudo cp /etc/letsencrypt/live/ceneca.yourcompany.com/privkey.pem certs/private.key
sudo chown $USER:$USER certs/*
```

## Security Notes

⚠️ **Important:**
- Keep `private.key` secure and never commit it to version control
- Use certificates from trusted CAs for production
- Self-signed certificates will trigger browser warnings
- Consider using certificate rotation/renewal processes 