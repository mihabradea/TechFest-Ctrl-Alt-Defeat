from .prompts import (
    CREATE_INVOICE_PROMPT,
    LIST_INVOICE_PROMPT,
    GET_INVOICE_PROMPT,
    SEND_INVOICE_PROMPT,
    SEND_INVOICE_REMINDER_PROMPT,
    CANCEL_SENT_INVOICE_PROMPT,
    GENERATE_INVOICE_QRCODE_PROMPT,
)



from .parameters import (
    CreateInvoiceParameters,
    SendInvoiceParameters,
    ListInvoicesParameters,
    GetInvoiceParameters,
    SendInvoiceReminderParameters,
    CancelSentInvoiceParameters,
    GenerateInvoiceQrCodeParameters,
)


from techfest.backend.agentic_ai.invoices.tool_handlers import (
    create_invoice,
    send_invoice,
    list_invoices,
    get_invoice,
    send_invoice_reminder,
    cancel_sent_invoice,
    generate_invoice_qrcode
)

from pydantic import BaseModel

tools = [
    
    {
        "method": "create_invoice",
        "name": "Create PayPal Invoice",
        "description": CREATE_INVOICE_PROMPT.strip(),
        "args_schema": CreateInvoiceParameters,
        "actions": {"invoices": {"create": True}},
        "execute": create_invoice,
    },
    
]
