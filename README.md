[![Docker Image Version](https://img.shields.io/docker/v/northwestnodes/otto-apruver?logo=docker&sort=semver)](https://hub.docker.com/r/northwestnodes/otto-apruver)
[![Docker Pulls](https://img.shields.io/docker/pulls/northwestnodes/otto-apruver?logo=docker)](https://hub.docker.com/r/northwestnodes/otto-apruver)
[![Docker Image Size](https://img.shields.io/docker/image-size/northwestnodes/otto-apruver/latest?logo=docker)](https://hub.docker.com/r/northwestnodes/otto-apruver)

# **Disclaimer**

This software is provided strictly **“as is”**, **“as available”**, and **“as you probably shouldn’t use it in production but will anyway.”**  
We make **no promises**, **no guarantees**, and **no warranties of any kind**, express or implied, regarding:

- functionality, reliability, security, or general emotional stability of the code  
- the continued existence of your Chainlink node  
- the integrity of your job specs  
- the uptime of your feeds  
- your ability to read a warning before blowing up your infrastructure  
- or your capacity to store credentials somewhere that isn’t a plaintext sticky note taped to your monitor  

By using this tool, you acknowledge that:

- If you nuke your Chainlink node, that’s on you.  
- If your Operator UI credentials leak because you decided `.env` files belong in GitHub, that’s on you.  
- If you accidentally approve 400 job specs at once and spend the rest of the evening crying into your keyboard, that’s also on you.  

Basically, **you break it, you bought it**, except you don’t even get a refund because we never sold you anything in the first place.

Use responsibly. Or don’t. Just don’t blame us.


# **Usage**

Env vars:

```
CL_NODE_URL = ""
CL_EMAIL = ""
CL_PASSWORD = ""
CL_FEEDS_MANAGER_ID = "1"
CL_NETWORK = "network name goes here, e.g. ethereum, ccip, arbitrum"
CL_APPROVABLE_STATES="PENDING,REQUIRES_ADMIN_APPROVAL,VERSION_PENDING,PROPOSED"
CL_INTERVAL = "60"
CL_SLACK_WEBHOOK = ""
```

Change variables accordingly.

Then just run the thing in a docker-compose or any which way you like.
