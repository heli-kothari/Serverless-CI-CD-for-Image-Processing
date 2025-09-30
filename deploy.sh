#!/bin/bash

set -e

ENVIRONMENT=${1:-dev}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "========================================="
echo "Deploying Image Processor to $ENVIRONMENT"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials are not configured properly."
    exit 1
fi

print_status "AWS credentials verified"

echo ""
echo "Step 1: Running tests..."
cd "$PROJECT_ROOT"

if [ -f "src/lambda/requirements.txt" ]; then
    python3 -m pip install -r src/lambda/requirements.txt -q
    python3 -m pip install pytest pytest-cov -q
    
    if python3 -m pytest src/tests/ -v; then
        print_status "All tests passed"
    else
        print_error "Tests failed. Deployment aborted."
        exit 1
    fi
else
    print_warning "No requirements.txt found, skipping tests"
fi

echo ""
echo "Step 2: Creating Lambda deployment package..."
mkdir -p "$PROJECT_ROOT/builds"

cd "$PROJECT_ROOT/src/lambda"
if [ -d "package" ]; then
    rm -rf package
fi
mkdir package

# Install dependencies
pip install -r requirements.txt -t package/ -q

# Create ZIP
cd package
zip -r "$PROJECT_ROOT/builds/lambda_function.zip" . > /dev/null
cd ..
zip -g "$PROJECT_ROOT/builds/lambda_function.zip" image_processor.py > /dev/null

print_status "Lambda package created: builds/lambda_function.zip"

echo ""
echo "Step 3: Initializing Terraform..."
cd "$PROJECT_ROOT/terraform"

if terraform init; then
    print_status "Terraform initialized"
else
    print_error "Terraform initialization failed"
    exit 1
fi

echo ""
echo "Step 4: Running Terraform plan..."
if terraform plan -var="environment=$ENVIRONMENT" -out=tfplan; then
    print_status "Terraform plan created"
else
    print_error "Terraform plan failed"
    exit 1
fi

echo ""
read -p "Do you want to apply this plan? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    print_warning "Deployment cancelled"
    exit 0
fi

echo ""
echo "Step 5: Applying Terraform changes..."
if terraform apply tfplan; then
    print_status "Terraform applied successfully"
else
    print_error "Terraform apply failed"
    exit 1
fi

echo ""
echo "========================================="
echo "Deployment Summary"
echo "========================================="
terraform output

print_status "Deployment completed successfully!"

echo ""
echo "Next steps:"
echo "1. Upload an image to the uploads/ folder in your upload bucket"
echo "2. Check the processed/ folder in your processed bucket"
echo "3. View Lambda logs in CloudWatch"
