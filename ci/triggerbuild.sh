#!/bin/bash
"$WORKSPACE/ciscripts/buildpending.sh"
if "$WORKSPACE/ciscripts/buildscript.sh"
then
  echo BUILD SUCCESS
else
  echo BUILD FAILURE
fi
