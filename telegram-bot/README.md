# DT Job Alerts Telegram publisher

Checks the configured employer/ATS feeds once per hour and publishes newly
discovered openings to `@dtjobalerts`. The first run—and the first run after a
new company source is added—records existing jobs without posting them,
preventing an initial flood.

The publisher uses Python 3.12 and only the Python standard library. There is no
Android, Firebase, Node.js, or third-party package dependency.

## Local setup

Put the replacement BotFather token in `telegram-bot/.env`:

```text
TELEGRAM_BOT_TOKEN=your_replacement_token
TELEGRAM_CHANNEL=@dtjobalerts
JOB_ALERTS_TIMEZONE=Europe/Athens
```

The `.env` file is ignored by Git and must never be committed or shared. Real
environment variables take precedence over values from the file.

To intentionally publish every currently open job on the first run, use:

```shell
python telegram-bot/job_alerts.py --post-existing
```

This can create hundreds of channel posts. Successful posts are checkpointed so
an interrupted run can be resumed without reposting completed jobs.

Messages show the date the collector first discovered the opening as `Found`.
Publication dates from the employer are not required or displayed.

Non-remote locations matching a case-insensitive rule in
`excluded-location-keywords.txt` are also recorded as seen without being posted.
Explicit `Remote` and `Work from Home` locations bypass these keyword rules.

## Validation

Fetch every configured source and print one representative live opening from
each company:

```shell
python telegram-bot/validate_sources.py
```

Each source is reported as `OK`, `EMPTY`, or `FAIL`. `EMPTY` means the source
responded successfully but has no current openings; only `FAIL` makes the
command exit nonzero. This command never posts to Telegram or changes
`seen-jobs.json`.

To collect and validate all jobs without printing one per source:

```shell
python telegram-bot/job_alerts.py --collect-only
```

## Code layout

- `job_alerts.py` owns environment loading, deduplication state, filtering, and
  Telegram publishing.
- `job_alerts_lib/sources.py` is the source registry.
- `job_alerts_lib/collector.py` runs sources concurrently and isolates failures.
- `job_alerts_lib/connectors/` contains ATS-specific integrations.
- `job_alerts_lib/http.py` and `job_alerts_lib/locations.py` contain shared
  dependency-free utilities.

## Temporary channel cleanup

Discover recent channel message IDs without deleting anything:

```shell
python telegram-bot/cleanup_channel.py
```

Review the count, then explicitly delete those messages:

```shell
python telegram-bot/cleanup_channel.py --delete
```

Telegram only permits bots to delete messages sent less than 48 hours ago. The
bot must retain the necessary channel administrator permissions. Telegram may
not return a bot's own channel posts through `getUpdates`; when `--delete` is
explicitly supplied and no IDs are found, the script posts a silent temporary
probe and deletes the channel message-ID range up to that probe.

## GitHub setup

1. Create a public GitHub repository and push this project.
2. Open **Settings → Secrets and variables → Actions**.
3. Add a repository secret named `TELEGRAM_BOT_TOKEN` containing the replacement
   token from BotFather. Never commit the token to this repository.
4. Open **Actions → Telegram job alerts → Run workflow**.
5. Confirm the first run succeeds. It seeds `seen-jobs.json` without sending.
6. Future scheduled runs post new jobs to the channel.

The bot must be a channel administrator with permission to post messages.
