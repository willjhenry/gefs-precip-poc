# Simple Lambda container for POC. Assumes x86_64 runtime.
# For TF compatibility, consider AWS Deep Learning Base images as a starting point.

FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Set workdir inside the image
WORKDIR /var/task

# Copy project code into image
# Note: For faster builds, you may tailor this to only what's needed
COPY . /var/task

# Install minimal dependencies
# Prefer building wheels in a builder image in production; this is POC-simple
# No OS-level ecCodes install: rely on ecmwflibs wheel bundled with cfgrib

RUN python -m pip install --upgrade pip \
    && python -m pip install --only-binary=:all: -r lambda/requirements.txt

# Default command sets the Lambda handler
CMD ["lambda.handler.lambda_handler"]
