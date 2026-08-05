# Scheduling

The digest command is noninteractive and can be scheduled by the host.

Cron example:

```cron
0 18 * * * KG_DATA_DIR=$HOME/.local/share/knowledge-garden KG_EMBED_BACKEND=fake /path/to/kg digest --hours 24 --output $HOME/knowledge-digest.md
```

A systemd user timer can run `kg digest --hours 24 --output %h/knowledge-digest.md` from a service with `KG_DATA_DIR` set in its environment. No scheduler daemon is included in this repository.
