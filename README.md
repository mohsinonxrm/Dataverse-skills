# Dataverse-skills

Agent skills and MCP configuration for Microsoft Dataverse — works with Claude Code and GitHub Copilot.

## Install

### Claude Code

```
/plugin marketplace add microsoft/Dataverse-skills
/plugin install dataverse@dataverse-skills
```

### GitHub Copilot

```
copilot plugin marketplace add microsoft/Dataverse-skills
copilot plugin install dataverse@microsoft/Dataverse-skills
```

Once the repo is publicly listed in [awesome-copilot](https://github.com/github/awesome-copilot), install simplifies to:

```
copilot plugin install dataverse@awesome-copilot
```

## What's included

- **7 skills** covering machine setup, workspace init, metadata authoring, solution management, Python SDK, MCP configuration, and demo data
- **MCP server** configuration for Dataverse Web API access
- **Scripts** for authentication and MCP client enablement
- **Templates** for CLAUDE.md project files

## Local development

Test the plugin locally without installing from a marketplace:

```bash
# Claude Code
claude --plugin-dir ./.github/plugins/dataverse

# GitHub Copilot
copilot plugin install ./.github/plugins/dataverse
```

## Contributing

This project welcomes contributions and suggestions. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

[MIT](LICENSE)

## Security

See [SECURITY.md](SECURITY.md) for reporting security vulnerabilities.
