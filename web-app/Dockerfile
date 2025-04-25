# in Docker, it is common to base a new image on a previously-created image
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    make \
    gcc \
    git \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pipenv

WORKDIR /app

COPY Pipfile .
COPY Pipfile.lock .

RUN pipenv install --deploy --system

# the ADD command is how you add files from your local machine into a Docker image
# Copy the current directory contents into the container at /app
ADD . .

# expose the port that the Flask app is running on... by default 5000
EXPOSE 5000

# Run app.py when the container launches
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]