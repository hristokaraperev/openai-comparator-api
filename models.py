from sqlalchemy import Table, Column, Integer, String
from database import metadata

cv_table = Table(
    "cvs", metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("file_name", String, index=True),
    Column("content", String), 
)

job_desc_table = Table(
    "job_descriptions", metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("file_name", String, index=True),
    Column("content", String),
)