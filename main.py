from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sqlalchemy import insert, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import engine, async_session, metadata
from models import cv_table, job_desc_table
from openai import OpenAI

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    # Shutdown ops to be placed here

app = FastAPI(lifespan=lifespan)
client = OpenAI()

class RankRequest(BaseModel):
    model: str
    cv_ids: list[int]
    job_desc_id: int

@app.post("/upload/cv/")
async def upload_cv(file: UploadFile = File(...)):
    content = await file.read()
    async with async_session() as session:
        async with session.begin():
            stmt = insert(cv_table).values(file_name=file.filename, content=content.decode())
            await session.execute(stmt)
    return {"filename": file.filename}

@app.post("/upload/job_description/")
async def upload_job_description(file: UploadFile = File(...)):
    content = await file.read()
    async with async_session() as session:
        async with session.begin():
            stmt = insert(job_desc_table).values(file_name=file.filename, content=content.decode())
            await session.execute(stmt)
    return {"filename": file.filename}

@app.get("/cvs/")
async def get_cvs():
    async with async_session() as session:
        result = await session.execute(select(cv_table))
        cvs = result.fetchall()
    return {"cvs": [{"id": row[0], "file_name": row[1]} for row in cvs]}

@app.get("/job_descriptions/")
async def get_job_descriptions():
    async with async_session() as session:
        result = await session.execute(select(job_desc_table))
        job_descriptions = result.fetchall()
    return {"job_descriptions": [{"id": row[0], "file_name": row[1]} for row in job_descriptions]}

@app.delete("/delete/cv/{cv_id}")
async def delete_cv(cv_id: int):
    async with async_session() as session:
        async with session.begin():
            stmt = delete(cv_table).where(cv_table.c.id == cv_id)
            await session.execute(stmt)
    return {"message": "CV deleted"}

@app.delete("/delete/job_description/{job_desc_id}")
async def delete_job_description(job_desc_id: int):
    async with async_session() as session:
        async with session.begin():
            stmt = delete(job_desc_table).where(job_desc_table.c.id == job_desc_id)
            await session.execute(stmt)
    return {"message": "Job Description deleted"}


@app.post("/rank_cvs/")
async def rank_cvs(request: RankRequest):
    async with async_session() as session:
        cv_result = await session.execute(select(cv_table).where(cv_table.c.id.in_(request.cv_ids)))
        cvs = cv_result.fetchall()
        job_desc_result = await session.execute(select(job_desc_table).where(job_desc_table.c.id == request.job_desc_id))
        job_description = job_desc_result.fetchone()
        
        cv_texts = "\n\n".join(row[2] for row in cvs)
        prompt = f"Rank the following CVs based on their match to the job description:\n\nJob Description:\n{job_description[2]}\n\nCVs:\n{cv_texts}"

        completion = client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": "You are a very experienced recruiter, who is going to provide advice about the best candidate for a job position."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return {"ranking": completion.choices[0].message}    