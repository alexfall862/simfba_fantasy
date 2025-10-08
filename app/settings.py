# # app/settings.py
# import os
# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     DATA_ROOT: str = os.path.abspath("./data")  # where your JSON lives
#     DATA_URL_PREFIX: str = "/data"              # must match StaticFiles mount
#     API_BASE: str = "https://simfba.azurewebsites.net/api/statistics/interface/v2"
#     ADMIN_BEARER_TOKEN: str = ""                # set in .env

# settings = Settings()  # import this everywhere
