REDIS_URL = "redis://:password@localhost:6379/0"
WAIT_AFTER_FILECHANGE = 5                       # in s, determines how long a scan is delayed
COLLECTIONS =  \
    {                                           # This creates 2 collections with different folders
        "test": \
        {                                       # 127.0.0.1:<port>/test/index                       
            "paths":        ["./test"],         # Include folder ./test
            "blacklist":    [".*\.c",".*\.py"], # Reject all .c or .py files
            "whitelist":    ["hello"]           # Only allow files with hello in it's name
        },                                      # uses re.match, see https://regex101.com/ for help
        "data": \
        {                                       # 127.0.0.1:<port>/data/index                       
            "paths":        ["./data"],         # Include folder ./data
            "blacklist":    [],                 #
            "whitelist":    []                  # The whitelist does NOT override the blacklist
        }
    }                                           # File Access is still over /md5/<md5> or /sha1/<sha1>


# TESTING = TRUE                                # For developement