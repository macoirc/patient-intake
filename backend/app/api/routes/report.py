import csv
import datetime
import logging
from io import StringIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlmodel import Session
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app import crud
from app.api import deps
from app.api.deps import SessionDep, get_current_active_superuser
from app.core.db import engine
from app.core.config import settings
from app.models import User
from app.utils import generate_weekly_report_email, send_email_with_attachment

router = APIRouter(prefix="/reports", tags=["reports"])

# Setup Jinja2 environment
env = Environment(loader=FileSystemLoader("app/pdf_engine/utils/"))

@router.get("/avg-duration")
def get_avg_duration(session: SessionDep):
    """
    Endpoint to get the average duration in hours between intake packet creation
    and reminder completion.
    """
    avg_duration = crud.get_avg_duration(session)
    if avg_duration is None:
        return {"avg_duration_hours": None}
    return {"avg_duration_hours": avg_duration}

@router.get("/incomplete-patients")
def get_incomplete_patients(session: SessionDep):
    """
    Endpoint to get the list of patients who have incomplete forms
    """
    incomplete_patients = crud.get_incomplete_patients(session)
    return {"incomplete_patients": incomplete_patients}

@router.get("/incomplete-forms")
def get_incomplete_forms(session: SessionDep):
    """
    Endpoint to get the summary of forms that have not yet
    been completed (i.e. status != COMPLETED or LINKED)
    """
    incomplete_forms = crud.get_incomplete_forms(session)
    return {"incomplete_forms": incomplete_forms}


@router.get("/download-pdf", response_class=Response)
def download_report_pdf(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
) -> Response:
    """
    Generate and download a PDF report on-demand.
    """
    # 1. Fetch data
    avg_duration = crud.get_avg_duration(session=session)
    incomplete_patients = crud.get_incomplete_patients(session=session)
    incomplete_forms = crud.get_incomplete_forms(session=session)

    # 2. Render the HTML template
    template = env.get_template("report.html")
    html_content = template.render(
        avg_duration_hours=avg_duration or 0,
        incomplete_patients=incomplete_patients,
        incomplete_forms=incomplete_forms,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        settings=settings,
    )

    # 3. Generate PDF from HTML
    pdf_bytes = HTML(string=html_content).write_pdf()

    # 4. Return the PDF as a response
    headers = {
        "Content-Disposition": f'attachment; filename="System_Report_{datetime.date.today()}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


def _build_csv_report(
    avg_duration: float | None,
    incomplete_patients: list,
    incomplete_forms: list,
    report_date: datetime.date,
) -> StringIO:
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow(["Section: Incomplete Patients"])
    writer.writerow(["patient_id"])
    for pid in incomplete_patients:
        writer.writerow([pid])
    writer.writerow([])

    writer.writerow(["Section: Missing Forms by Type"])
    writer.writerow(["form_name", "incomplete_count"])
    for form in incomplete_forms:
        writer.writerow([form["form_name"], form["count"]])
    writer.writerow([])

    writer.writerow(["Section: Summary"])
    writer.writerow(["metric", "value"])
    writer.writerow(["Average Intake Duration (hrs)", avg_duration or "N/A"])
    writer.writerow(["Report Generated", report_date.isoformat()])
    output.seek(0)
    return output


@router.get("/download-csv")
def download_report_csv(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
) -> StreamingResponse:
    """
    Generate and download a CSV report on-demand.
    """
    avg_duration = crud.get_avg_duration(session=session)
    incomplete_patients = crud.get_incomplete_patients(session=session)
    incomplete_forms = crud.get_incomplete_forms(session=session)
    output = _build_csv_report(
        avg_duration, incomplete_patients, incomplete_forms, datetime.date.today()
    )
    filename = f"System_Report_{datetime.date.today()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(output, media_type="text/csv", headers=headers)


def generate_and_save_report() -> None:
    """
    Job to be run on a schedule.
    Generates the weekly report and saves it to a file.
    """
    logging.info("Scheduler: Running weekly report generation job.")
    with Session(engine) as session:
        try:
            # 1. Fetch data
            avg_duration = crud.get_avg_duration(session=session)
            incomplete_patients = crud.get_incomplete_patients(session=session)
            incomplete_forms = crud.get_incomplete_forms(session=session)

            # 2. Render HTML template
            template = env.get_template("report.html")
            crud.log_action(
                session=session,
                user="Scheduler",
                action="Generating weekly report..."
            )
            report_date = datetime.date.today()
            html_content = template.render(
                avg_duration_hours=avg_duration or 0,
                incomplete_patients=incomplete_patients,
                incomplete_forms=incomplete_forms,
                generated_at=report_date.strftime("%Y-%m-%d"),
                settings=settings,
            )

            # 3. Generate and save PDF
            pdf_bytes = HTML(string=html_content).write_pdf()
            pdf_filename = f"System_Report_{report_date.strftime('%Y-%m-%d')}.pdf"
            storage_path = Path(settings.PDF_STORAGE_DIR) / "reports"
            storage_path.mkdir(parents=True, exist_ok=True)
            file_path = storage_path / pdf_filename
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            crud.log_action(
                session=session,
                user="Scheduler",
                action=f"Weekly report saved to {file_path}")

            # Email CSV report if a recipient is configured
            if settings.emails_enabled and settings.WEEKLY_REPORT_EMAIL:
                try:
                    csv_output = _build_csv_report(
                        avg_duration, incomplete_patients, incomplete_forms, report_date
                    )
                    csv_bytes = csv_output.getvalue().encode("utf-8")
                    email_data = generate_weekly_report_email(
                        avg_completion_time=avg_duration,
                        incomplete_patient_count=len(incomplete_patients),
                        report_date=report_date.isoformat(),
                    )
                    send_email_with_attachment(
                        email_to=settings.WEEKLY_REPORT_EMAIL,
                        subject=email_data.subject,
                        html_content=email_data.html_content,
                        attachment_data=csv_bytes,
                        attachment_filename=f"System_Report_{report_date}.csv",
                    )
                    logging.info(f"Scheduler: Weekly report emailed to {settings.WEEKLY_REPORT_EMAIL}")
                except Exception as email_err:
                    logging.error(f"Scheduler: Failed to send weekly report email: {email_err}")
            else:
                logging.info("Scheduler: WEEKLY_REPORT_EMAIL not configured; skipping email.")

            session.commit()
        except Exception as e:
            logging.error(f"Scheduler: Error generating or saving report: {e}", exc_info=True)
            # The 'with' statement will automatically handle session rollback on exception


@router.get("/saved-reports", response_model=list[str])
def list_saved_reports(
    current_user: User = Depends(get_current_active_superuser),
) -> list[str]:
    """List all generated PDF reports."""
    storage_path = Path(settings.PDF_STORAGE_DIR) / "reports"
    if not storage_path.exists():
        return []
    report_files = [f.name for f in storage_path.iterdir() if f.is_file() and f.suffix == ".pdf"]
    return sorted(report_files, reverse=True)


@router.get("/saved-reports/{filename}", response_class=FileResponse)
def get_saved_report(
    filename: str,
    current_user: User = Depends(get_current_active_superuser),
) -> FileResponse:
    """Download a specific generated PDF report."""
    storage_path = Path(settings.PDF_STORAGE_DIR) / "reports"
    file_path = storage_path / filename

    if not file_path.is_file() or not file_path.resolve().parent == storage_path.resolve():
        raise HTTPException(status_code=404, detail="Report not found or invalid filename.")

    return FileResponse(path=file_path, filename=filename, media_type="application/pdf")
