# Dataverse-skills

Agent skills and MCP configuration for Microsoft Dataverse — works with Claude Code and GitHub Copilot.

## Install

### Claude Code

```
/plugin marketplace add microsoft/Dataverse-skills
/plugin install dataverse@dataverse-skills
```

### GitHub Copilot

Available via [awesome-copilot](https://github.com/github/awesome-copilot) as the `dataverse` plugin.

## What's included

- **7 skills** covering machine setup, workspace init, metadata authoring, solution management, Python SDK, MCP configuration, and demo data
- **MCP server** configuration for Dataverse Web API access
- **Scripts** for authentication and MCP client enablement
- **Templates** for CLAUDE.md project files

## Local development

Test the plugin locally without installing from a marketplace:

```bash
claude --plugin-dir ./.github/plugins/dataverse
```

## Contributing

This project welcomes contributions and suggestions. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

[MIT](LICENSE)

## Security

See [SECURITY.md](SECURITY.md) for reporting security vulnerabilities.
