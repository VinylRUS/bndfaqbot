from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.ticket_repo import TicketRepository
from app.database.repositories.audit_log_repo import AuditLogRepository


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ticket_repo = TicketRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def export_tickets_to_excel(self, admin_id: int) -> io.BytesIO:
        tickets = await self.ticket_repo.get_all_for_export()

        data = []
        for ticket in tickets:
            data.append(
                {
                    "ID": ticket.id,
                    "Номер": ticket.number,
                    "Дата создания": ticket.created_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.created_at else "",
                    "Дата закрытия": ticket.closed_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.closed_at else "",
                    "Категория": ticket.category.full_name if ticket.category else "",
                    "Статус": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                    "Пользователь": ticket.author.display_name if ticket.author else "",
                    "Телефон": ticket.author.phone if ticket.author else "",
                    "Оператор": ticket.operator.display_name if ticket.operator else "",
                    "Оценка": ticket.rating.score if ticket.rating else "",
                    "Текст обращения": ticket.text,
                }
            )

        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Обращения")
            worksheet = writer.sheets["Обращения"]
            for idx, col in enumerate(worksheet.columns):
                max_length = max(
                    len(str(cell.value)) if cell.value else 0
                    for cell in col
                )
                worksheet.column_dimensions[
                    worksheet.cell(row=1, column=idx + 1).column_letter
                ].width = min(max_length + 2, 50)

        buffer.seek(0)

        await self.audit_repo.create(
            user_id=admin_id,
            role="admin",
            action="export_tickets",
            object_type="ticket",
            details="Exported tickets to Excel",
        )

        return buffer
