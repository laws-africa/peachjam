# Peach Jam Pro

Select peachjam websites that need more advanced deployment options.

# Production deployment

See [peachjam/DEPLOYMENT.md](https://github.com/laws-africa/peachjam/blob/main/DEPLOYMENT.md) for details.

Requires a GitHub Personal Access Token to clone certain libraries from the Laws.Africa github repo. Substitute the <TOKEN> below:

```
dokku docker-options:add <APP-NAME> build "--build-arg GITHUB_PAT=<TOKEN>"
```

# License

Copyright 2023 Laws.Africa.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
