# Distributed Mini Twitter on AWS

Cloud Computing Final Project Presentation Script

## 1. Opening

```text
Hi everyone, today I will present my final project.

This project is a Mini Twitter system deployed on AWS. Users can register, log in, post tweets, follow other users, view their home timeline, like tweets, edit their profile, and delete their own tweets.

Behind the website, the system is built with four microservices: Gateway Service, User Service, Tweet Service, and Timeline Service. These services are containerized with Docker and deployed on ECS Fargate. I also use RDS PostgreSQL for persistent data, Redis for caching and rate limiting, S3 for the frontend, and AWS CDK to define the infrastructure.

I will start with a quick code structure review, because the codebase is organized based on the cloud architecture. Then I will briefly show the AWS deployment, and finally I will demonstrate the website features.
```

## 2. Presentation Flow

Recommended order:

1. Opening introduction
2. Code structure review
3. AWS deployment verification
4. Website feature demo
5. Final summary

Suggested timing:

| Section | Time |
| --- | --- |
| Opening | 1 min |
| Code structure review | 4-5 min |
| AWS deployment verification | 1-2 min |
| Website demo | 5-7 min |
| Final summary | 30 sec |

## 3. Code Review Introduction

Before opening the code, say:

```text
Before I jump into the code, I want to give a quick overview of how this project is organized.

This project is a cloud-deployed microservice application. The codebase is structured to match the cloud architecture. At the top level, there are five main parts: infrastructure code, backend microservices, database schema, frontend application, and local testing tools.

During the code review, I will not go line by line. Instead, I will show how each folder maps to one part of the cloud system.
```

## 4. Code Structure Review

### 4.1 Infrastructure Code

Open:

```text
cdk/
cdk/stacks/
```

Say:

```text
First, the cdk folder contains the infrastructure as code. This is where I define the AWS resources instead of manually creating them in the AWS Console.

I split the infrastructure into four stacks.
```

Point to:

```text
cdk/stacks/network_stack.py
cdk/stacks/database_stack.py
cdk/stacks/container_stack.py
cdk/stacks/frontend_stack.py
```

Say:

```text
NetworkStack creates the VPC, public and private subnets, and security groups.

DatabaseStack creates RDS PostgreSQL and ElastiCache Redis.

ContainerStack creates the ECS Fargate cluster, Application Load Balancer, Cloud Map service discovery, and the four backend services.

FrontendStack creates the S3 static website for the React frontend.

This part is the foundation of the cloud deployment. It defines where the system runs, how services are networked, and which resources are public or private.
```

### 4.2 Backend Microservices

Open:

```text
services/
```

Say:

```text
Next, the services folder contains the backend microservices. Each service has its own main.py, Dockerfile, and requirements.txt, so each service can be built and deployed as an independent container.
```

Point to:

```text
services/gateway/
services/user/
services/tweet/
services/timeline/
```

Say:

```text
Gateway is the API entry point. It routes requests to the correct internal service and handles rate limiting.

User handles registration, login, JWT authentication, user profiles, and follow relationships.

Tweet handles creating tweets, deleting tweets, likes, and fan-out-on-write into Redis timelines.

Timeline handles home timeline and user timeline reads. It checks Redis first and falls back to PostgreSQL if needed.

This structure reflects the microservice design. Each service owns a specific responsibility instead of putting all backend logic into one monolithic application.
```

### 4.3 Database Schema

Open:

```text
db/migrations/
```

Say:

```text
The db/migrations folder contains the PostgreSQL schema.

The main tables are users, tweets, follows, likes, and like_count_pending.

PostgreSQL is used as the durable source of truth. Redis is used separately for cached timelines, gateway rate limiting, and temporary like count updates.

The database layer separates durable state in PostgreSQL from fast temporary state in Redis.
```

### 4.4 Frontend Application

Open:

```text
frontend/src/
```

Say:

```text
The frontend folder contains the React application. After build, it is deployed to S3 as a static website.
```

Point to:

```text
frontend/src/api.js
frontend/src/App.jsx
frontend/src/components/
```

Say:

```text
api.js is the central API wrapper. In production, it points to the ALB URL and sends requests through the /v1 backend API.

App.jsx manages authentication state and switches between the main views: Home, Users, and Profile.

The components folder contains the user-facing features such as login, tweet box, feed, user search, and profile.

The frontend is mainly used to demonstrate that the deployed backend works end to end.
```

### 4.5 Local Development and Testing

Open:

```text
docker-compose.yml
scripts/test_api.py
```

Say:

```text
For local development, docker-compose.yml can run PostgreSQL, Redis, and all four backend services on my machine.

scripts/test_api.py contains API tests to verify important workflows before deployment, such as register, login, tweeting, following, timeline loading, and likes.

This helps me test the system locally before deploying the same service structure to AWS.
```

### Code Review Closing

Say:

```text
To summarize the code review: the codebase is organized in the same way as the cloud architecture. CDK defines the AWS infrastructure, services contains the containerized microservices, db/migrations defines the PostgreSQL schema, frontend contains the S3-hosted React app, and Docker Compose plus tests support local development.
```

## 5. AWS Deployment Verification

Transition:

```text
After reviewing the code structure, I want to briefly show that these CDK stacks are actually deployed on AWS.
```

### 5.1 CloudFormation

Open AWS Console:

```text
CloudFormation -> Stacks
```

Show stacks:

```text
NetworkStack
DatabaseStack
ContainerStack
FrontendStack
```

Say:

```text
Here are the CloudFormation stacks generated by AWS CDK. Each stack corresponds to one part of the infrastructure: network, database, containers, and frontend.

The stack status shows that the infrastructure has been successfully deployed.
```

### 5.2 ECS

Open:

```text
ECS -> Cluster -> Services
```

Show:

```text
Gateway
User
Tweet
Timeline
```

Say:

```text
Here are the four backend microservices running as ECS Fargate services. Each service is deployed as an independent container.
```

### 5.3 Application Load Balancer

Open:

```text
EC2 -> Load Balancing -> Load Balancers
```

Or:

```text
CloudFormation -> ContainerStack -> Resources -> Alb
```

Show:

```text
DNS name
Listeners and rules
```

Say:

```text
This is the public Application Load Balancer DNS. Backend API requests go through this address.

Here we can also see the HTTP listener and path-based routing rules created by CDK.
```

### 5.4 Data Layer and Frontend

Optionally show:

```text
RDS PostgreSQL
ElastiCache Redis
S3 frontend bucket
```

Say:

```text
The data layer includes RDS PostgreSQL for durable storage and ElastiCache Redis for caching.

The React frontend is built as static files and hosted on S3.
```

Transition to demo:

```text
Now that we have verified the AWS deployment, I will open the frontend website and demonstrate the main features.
```

## 6. Website Demo Script

Demo style: keep this part focused on user features. Do not explain backend internals unless asked.

Opening:

```text
Now I will demonstrate the main features of the website using two users, Bob and Alice.
```

### 6.1 Login as Bob

Action:

```text
Login as Bob.
```

Say:

```text
First, I log in as Bob.
```

### 6.2 Bob Posts a Tweet

Action:

```text
Bob posts: Hello from Bob!
```

Say:

```text
Bob can create a tweet from the Home page.
```

### 6.3 Logout Bob

Action:

```text
Click Log out.
```

Say:

```text
Now I log out from Bob's account.
```

### 6.4 Login as Alice

Action:

```text
Login as Alice.
```

Say:

```text
Next, I log in as Alice.
```

### 6.5 Alice Posts a Tweet

Action:

```text
Alice posts: Hello from Alice!
```

Say:

```text
Alice can also create her own tweet.
```

### 6.6 Alice Searches Bob

Action:

```text
Go to Users.
Search bob.
```

Say:

```text
Now Alice searches for Bob from the Users page.
```

### 6.7 Alice Follows Bob

Action:

```text
Click Follow.
```

Say:

```text
Alice can follow Bob.
```

### 6.8 Home Timeline

Action:

```text
Go back to Home.
Show Bob's tweet in Alice's timeline.
```

Say:

```text
After following Bob, Alice can see Bob's tweet in her Home timeline.
```

### 6.9 Like Bob's Tweet

Action:

```text
Alice likes Bob's tweet.
```

Say:

```text
Alice can like Bob's tweet.
```

### 6.10 Refresh Page

Action:

```text
Refresh the browser page.
```

Say:

```text
After refreshing the page, the tweet and like state are still there.
```

### 6.11 Alice Profile

Action:

```text
Go to Profile.
Show Alice's profile and following count.
```

Say:

```text
Now I open Alice's profile. Here we can see Alice's profile information and her following count.
```

### 6.12 Edit Profile

Action:

```text
Update display name:
Alice Cloud Demo

Update bio:
Testing the Mini Twitter app.
```

Say:

```text
Alice can update her display name and bio.
```

### 6.13 Delete Alice's Tweet

Action:

```text
Find Alice's own tweet.
Click Delete.
```

Say:

```text
Alice can delete her own tweet from her profile.
```

### Demo Closing

Say:

```text
This completes the demo. The website supports login, posting tweets, following users, home timeline, likes, profile update, and deleting tweets.
```

## 7. Final Summary

Say:

```text
To summarize, this project is a cloud-deployed Mini Twitter application. The frontend is hosted on S3, the backend runs as four ECS Fargate microservices, the Application Load Balancer exposes the API, RDS PostgreSQL stores persistent data, Redis supports caching and rate limiting, and AWS CDK defines the infrastructure as code.

The main purpose of the project is to demonstrate how a cloud-native application can be designed, deployed, and tested using AWS services.
```

## 8. Backup Short Version

If time is limited, use this shorter flow:

```text
Hi everyone, today I will present my final project, a Mini Twitter system deployed on AWS.

The codebase has five main parts. The cdk folder defines AWS infrastructure. The services folder contains four backend microservices. The db/migrations folder defines the PostgreSQL schema. The frontend folder contains the React app hosted on S3. Docker Compose and test scripts are used for local development.

In AWS, CDK deploys CloudFormation stacks for the network, database, containers, and frontend. The backend services run on ECS Fargate, the database is RDS PostgreSQL, Redis is used for caching, and the frontend is hosted on S3.

For the demo, I will log in as Bob, create a tweet, then log in as Alice, follow Bob, view Bob's tweet in Alice's home timeline, like the tweet, edit Alice's profile, and delete Alice's own tweet.
```
