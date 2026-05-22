#!/bin/sh
set -e
chown -R smdr:smdr /app/data
exec gosu smdr "$@"
