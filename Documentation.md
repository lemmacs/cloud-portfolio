# System Explanation and Definition:

### The static site is stored in S3 (Simple Storage Service) and delivered through CloudFront.

    - S3 is a highly scalable and serverless cloud object storage service provided by AWS. EC2 (Elastic Compute Cloud) instance wasn't used for this particular site because it is a static website and there isn't much logic to be processed in the backend. S3 was sufficient and still remains scalable, whereas EC2 would've added unnecessary infrastracture and cost.

    - CloudFront is a fast, globally distributed Content Delivery Network (CDN) service offered by AWS. It accelerates the delivery of static and dynamic web content, APIs, and videos.

### CloudFront OAC configuration helps secure the S3 bucket so it doesn't need to be publicly accessible.

    - CloudFront has a securuity feature called OAC (Origin Access Control) that protects your Amazon S3 buckets so users cannot access your files directly via the raw S3 URL. 

### Using the least-privilege IAM policy for Lambda only allows the DynamoDB operations it needs.

    - AWS IAM (Identity and Access Management) is a web service that helps you safely control who can access your AWS resources and what actions they can perform. Least-privilege only allows the minimum permissions they need to do their job and nothing more.

### GitHub Actions handles deployements whenever any change was pushed to the main branch.

    - GitHub Actions is a continuous integration and continuous delivery (CI/CD) and automation platform built directly into GitHub.

### There was also a serverless visitor counter added using API Gateway, Lambda, and DynamoDB.

    - Amazon API Gateway is a fully managed AWS service that acts as the "front door" for applications to access data, logic, or backened services. It allows the creation, publishing, maintainance, monitoring, and security of REST, HTTP, and WebSocket APIs at any scale.

    - AWS Lambda is a "serverless" compute service provided by AWS that allows you to run code without provisioning or managing any servers.

    - DynamoDB is a serverless, fully managed NoSQL database service provided by AWS that is optimized for operational applications requiring consistent, single digit millisecond latency at any scale.


# Work Flow

There are two separate flows happening:

### Deployement -----------------------User Request
        ↓----------------------------------↓
     GitHub---------------------------User's Browser
        ↓----------------------------------↓
    GitHub Actions---------------------CloudFront
        ↓----------------------------------↓
       S3----------------------------------S3
        ↓----------------------------------↓
    CloudFront cache---------------------Portfolio 
     invalidation

So CloudFront mainly acts as a delivery layer in front of S3 that securely serves the contents through the OAC. The security comes from how CloudFront and OAC are configured.

NOTE:

right now, we have an event the fires when we click on the words2motion live demo button. It records the time, date, and the name of the project that was clicked. This lives in the js script.