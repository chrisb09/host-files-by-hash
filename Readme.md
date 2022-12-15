This simple flask project calculates hashes of files in specified folders and offers these files via http for simple and convenient file sharing using md5 or sha1 hashes to identify the files. It also offers a simplistic index page that lists hashes, filename and size. For a fast performance redis is used.
I highly recommend using the included docker-compose file to deploy this script as it also sets up redis out-of-the-box
Additionally, the docker-compose file includes a TOR image, allowing for the file sharing to work anonymously via TOR, although the speeds will be significantly lower. Still, for anyone who cannot forward ports in their firewall this can be quite useful.


# Use

The project can be run with redis and a tor instance for hosting via a tor hidden service with

```docker-compose up -d```

It makes sense to configure the included paths though.

You can find the index page on
`localhost:7222/index` or `<address.onion>/index` (see below how to figure out your address)

The files are accessible via md5 or sha1 hashes via
```http://localhost:7222/md5/<md5_hash>```
or
```http://localhost:7222/sha1/<sha1_hash>```

The same 


# Configure

The following is the relevant excerpt from the `docker-compose.yml`

```yaml
    environment:
      - WAIT_AFTER_FILECHANGE=5
      - SOURCE_FILES=["/test","/data"]
      - REDIS_HOST=redis-host-file-by-hash
      - REDIS_HOST_PASSWORD=redis1234
      - REDIS_URL=redis://:redis1234@redis-host-file-by-hash:6379/0
    volumes:
      - ./data:/data:ro
      - ./test:/test:ro
```

All folders that should be included have to be specified in the `SOURCE_FILES` array, and also need to be mapped to the container under the `volumes` entry. Adding `:ro` (for read-only) ensures that your data cannot be modified even though this simple project does not do that to begin with. But hindsight is 20/20 so i employ you to use appropriately tight permissions whenever possible.

## Specifying a TOR address

You can specify a private `key` to have a constant .onion address.

You need to add the following environment variable to the tor container:

`SERVICE1_TOR_SERVICE_KEY: 'key'`

where key is the base64 encoded secret key of your onion address.

### Example

```yaml
tor:
    container_name: tor-host-file-by-hash
    image: goldy/tor-hidden-service:0.3.5.8
    links:
      - host-file-by-hash
    environment:
        SERVICE1_TOR_SERVICE_HOSTS: 80:host-file-by-hash:7222
        # tor v3 address private key base 64 encoded
        SERVICE1_TOR_SERVICE_KEY: 'PT0gZWQyNTUxOXYxLXNlY3JldDogdHlwZTAgPT0AAACArobDQYyZAWXei4QZwr++j96H1X/gq14NwLRZ2O5DXuL0EzYKkdhZSILY85q+kfwZH8z4ceqe7u1F+0pQi/sM'
```

This would make your service available on `xwjtp3mj427zdp4tljiiivg2l5ijfvmt5lcsfaygtpp6cw254kykvpyd.onion`

:warning: Do NOT use this publically known key, generate your own!

### Generate a private TOR key

There are many tools to do this, but I'd recommend using torpy as it is the same program used by the tor container

Install it with
```bash
pip install pytor
```

and generate a new key & address with
```bash
pytor new
```

The output is already b64 encoded, therefore you can simply paste the private key into `the docker-compose.yml`.

It is noteworthy that for some reason the tor container is picky about which keys it accepts and which not, so if you come accross the
`Private key does not seems to be a valid ed25519 tor key` error message the best option is to generate a new key until you get one it works.


For more information: https://github.com/cmehay/docker-tor-hidden-service/blob/master/README.md

## No TOR

If you do not need the TOR-hidden service, just delete the entire part from the `Dockerfile`.

# Get onion address

To use a hidden service you need to know on which address you are hosting your site. This can be determined with:

```sh
docker exec -ti tor-host-file-by-hash onions
```

Example output:
`http://hillxo4paitohwqltz44oopcyldcrl6gt7dmrl5c65h5r4njwp4jgsid.onion/`

# TO-DO

- [x] Allow for whitelist/blacklists for files
- [ ] Make index-page optional
- [ ] Allow for passwords for files/folders or index page
- [ ] Allow for cookie based authentication
- [ ] Allow for client-side sorting in index page
- [ ] Allow for option to disable md5/sha1 hashing
- [x] Put rendering of index file into seperate static files etc.
- [ ] Prerender index file whenever changes happen to improve performance
- [x] list render time and amount of entries in index
- [x] Proper exit handling (stop worker)
- [ ] Allow for hash-caching to be disabled
- [x] Calculate and serve thumbnails