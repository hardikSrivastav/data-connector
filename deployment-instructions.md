# AWS Deployment Setup

## Prerequisites

1. AWS account with appropriate permissions
2. GitHub repository for your project
3. EC2 instance running in AWS with Docker and Docker Compose installed

## Setting Up GitHub Secrets

Add the following secrets to your GitHub repository:

1. Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

2. Add these required secrets:

   - `AWS_ACCESS_KEY_ID`: Your AWS IAM user access key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS IAM user secret access key
   - `AWS_REGION`: The AWS region (e.g., us-east-1)
   - `EC2_HOST`: Public IP or DNS of your EC2 instance
   - `EC2_USERNAME`: SSH username (typically 'ec2-user' or 'ubuntu')
   - `EC2_SSH_KEY`: Your private SSH key to connect to the EC2 instance
   - `RAZORPAY_KEY_ID`: Your Razorpay key ID
   - `RAZORPAY_KEY_SECRET`: Your Razorpay key secret

## Setting Up AWS ECR (Elastic Container Registry)

1. Create a new repository in ECR named "ceneca"
   ```bash
   aws ecr create-repository --repository-name ceneca --region your-region
   ```

2. Make sure your IAM user/role has permissions to push to ECR

## Setting Up EC2 Instance

1. Launch an EC2 instance with sufficient resources
2. Install Docker and Docker Compose:
   ```bash
   sudo yum update -y
   sudo amazon-linux-extras install docker
   sudo service docker start
   sudo usermod -a -G docker ec2-user
   sudo chkconfig docker on
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

3. Clone your repository on the EC2 instance:
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   ```

4. Make sure the repository path matches the path in the GitHub Actions workflow file

## Testing Your Deployment

1. Make a change to your repository
2. Push it to the main branch
3. Go to GitHub → Actions to see the workflow running
4. Verify deployment on your EC2 instance

## Troubleshooting

If the deployment fails:
1. Check GitHub Actions logs for errors
2. Verify your secrets are correctly set up
3. Check EC2 instance for Docker or permission issues using `docker-compose logs` 