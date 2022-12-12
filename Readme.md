
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

You can specify a private key to have a constant .onion address.
How this can be done you can read up here: https://github.com/cmehay/docker-tor-hidden-service/blob/master/README.md

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

* Make index-page optional
* Allow for passwords for files/folders or index page
* Allow for cookie based authentication
* Allow for client-side sorting in index page
* Allow for option to disable md5/sha1 hashing