# ![f2ap](logo.svg)

[![Coverage Status](https://coveralls.io/repos/github/Deuchnord/f2ap/badge.svg?branch=main)](https://coveralls.io/github/Deuchnord/f2ap?branch=main)

f2ap (_Feed to ActivityPub_) is a web application that uses the RSS/Atom feed of your website to expose it on the Fediverse
through ActivityPub.

## Social platform compatibility

Even though ActivityPub is a generic protocol designed to be platform-agnostic, each social platform has its own particularities that f2ap has to comply with to be able to communicate with it.

Check [the compatibility table](https://github.com/Deuchnord/f2ap/wiki/Social-platforms-compatibility) on the wiki to see the progression.

## How to use it

### Prerequisite

The only prerequisite to use f2ap is that your website provides an RSS or Atom feed.
If you don't have one yet, you might want to make it first, as it is a Web standard that allows your visitors to stay in touch with your content with any compatible application. Plus, it is very easy to implement. 

### Installation

#### With PyPI

_**Required:** Python 3.9+_

Install the `f2ap` package:

```bash
pip install f2ap
```

The application will be runnable with the `f2ap` command.
You will need to use a runner like systemd to start it as a service.

#### Docker

_**Required:** Docker_

Grab the image from Docker Hub:

```bash
docker pull deuchnord/f2ap
```

You can get a specific version with the following syntax: `deuchnord/f2ap:<tag>`, where tag is one of the following (`i`, `j` and `k` being numbers):
- `latest`: the last version (default)
- `i`: the last version of the `i` major version
- `i.j`: the last version of the `i.j` minor version
- `i.j.k`: the version `i.j.k`
- `unstable`: the last commit in the Git history.
  It is heavily discouraged to use it in production, as it can have bugs, crash, put fire in your house or, worse, kill your kitten.

##### Docker-Compose

If you want to use f2ap through Docker-Compose, check the [`docker-compose.dist.yml`](docker-compose.dist.yml) for an example of configuration.

### Configuration

To make f2ap work, you will need to write a configuration file that will define its behavior.
It is a boring simple TOML file. You can find a self-documented file in [config.dist.toml](config.dist.toml).
If you run f2ap with Docker, make sure to name it `config.toml` and to place it in the `/data` folder.

### Configuring the server

To provide a better integration to your website, you are encouraged to add some configuration lines to your server.
This will ensure the social applications will correctly discover your website's ActivityPub API.

#### Nginx

Edit your configuration file and add the following lines to your `server` section.
Don't forget to adapt:
- the IP address on the `proxy_pass` lines to match f2ap's configuration;
- the `<username>` part in the last `location` to match the username of your actor.

```nginx
server {
    ## ...
    
    # Propagate the domain name to f2ap
    proxy_set_header Host $host;
    
    # The webfinger allows the social applications to find out that your website serves an ActivityPub API.
    location /.well-known/webfinger {
        proxy_pass http://127.0.0.1:8000;
    }
    
    location / {
        # Match any request asking for an ActivityPub content
        if ( $http_accept ~ .*application/activity\+json.* ) {
            proxy_pass http://127.0.0.1:8000;
        }

        # Match any request sending an ActivityPub content
        if ( $http_content_type = "application/activity+json" ) {
            proxy_pass http://127.0.0.1:8000;
        }
    }
    
    ## ... 
}
```

### Limitations

Because f2ap uses your RSS/Atom feed to connect your website to ActivityPub, the time before a new entry pops on the Fediverse will depend on the refresh frequency. You might want to choose a frequency that matches your update regularity.
  
**If this behavior is a problem**, f2ap is probably not the right solution for you, and you might need to integrate ActivityPub to your application on your own.
