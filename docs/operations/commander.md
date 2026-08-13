# Commander prototype operations

The first vertical slice is a local, standard-library Python module. It writes
an append-only JSONL event stream and a projection snapshot to a chosen output
directory. It does not contact Telegram, Instagram, or any AI provider.

Run from the repository root:

```sh
python3 -m commander.demo --output-dir .local/commander-demo
```

Run tests:

```sh
python3 -m unittest discover -s tests/commander -v
```

The output directory is disposable demonstration state and is ignored by Git.
For a service deployment, apply `db/migrations/001_commander_foundation.sql` to
PostgreSQL and implement the repository port against those tables. Do not run
the demo JSONL store concurrently from multiple processes.

Emergency stop and approval checks are policy gates in the domain service.
Telegram will be an authenticated transport adapter over the same command API;
it must not bypass those gates.
