[![log github events](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/event-logger.yml/badge.svg)](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/event-logger.yml)
[![Client CI](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/client-tester.yml/badge.svg)](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/client-tester.yml)
[![Web-App-CI](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/web-app-tester.yml/badge.svg)](https://github.com/software-students-spring2025/5-final-dot-ics/actions/workflows/web-app-tester.yml)

# ICS File Generator

ICS File Generator is a web app that generates a calender event file based on a description of an event. The app connects to a large language model that extracts key event information (event name, date, time, location, etc.) from plain text inputted by the user and then generates a calendar event for the user. The app allows users to use abbreviations such as "tmr" and "nxt" in their event descriptions, which are not supported by apps such as Apple Calendar. A user can create an account to store all the events that they created, as well as delete unwanted entries. Users are also able to download the calendar .ics file, which can then be imported into their calendar app.

## Temporary Deployment Link

*Deployed with a DigitalOcean Droplet.*

http://178.128.145.113:10000/

## DockerHub Container Links

- [ics-client](https://hub.docker.com/r/bdeweesevans/ics-client)
- [web-app](https://hub.docker.com/r/bdeweesevans/web-app)

## Authors

- [Shayne Chan](https://github.com/shayne773)
- [Jessica Chen](https://github.com/jessicahc)
- [Benjamin DeWeese](https://github.com/bdeweesevans)
- [Apollo Wyndham](https://github.com/a-wyndham1)

## Developer Instructions

1. Clone the git repository
   `git clone https://github.com/software-students-spring2025/5-final-dot-ics.git`
2. Create .env files for the web app and machine learning client
   - See [instructions](#environent-variables) below
3. Install Docker and [Docker Desktop](https://www.docker.com/products/docker-desktop/)
4. Open a terminal in the base repository of the project
5. Run the following command to start the web app, machine learning client, and MongoDB database
   - `docker compose up --build`
   - If you make any changes to the docker-compose file or Dockerfiles run `docker compose up --force-recreate --build`
6. Now you can view the web app at `http://localhost:10000/`
   - You can change this port in `docker-compose.yaml` and in the two `.env` files
7. Run the following command to stop and remove the containers
   - `docker compose down`
   - Note that after any code changes you must compose down and then complete step 5 to apply them

### Environent variables

Both the web app and machine learning client require `.env` files to function. Follow the example files below to create your own versions. It is vital to include the same fields, but insert your personal uri and database name for MongoDB as well as a [Gemini API Key](https://ai.google.dev/gemini-api/docs/api-key).

1. [Example `.env` for the web app](web-app/.env.example)
2. [Example `.env` for the machine learning client](ics-client/.env.example)
