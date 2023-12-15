docker compose down
docker volume rm steam-group-queue-discord-bot_postgres_data
docker compose build
# docker compose up -d
# docker container stop discord_bot