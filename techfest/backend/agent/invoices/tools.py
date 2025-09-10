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


from invoices.tool_handlers import (
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
    {
        "method": "list_invoices",
        "name": "List Invoices",
        "description": LIST_INVOICE_PROMPT.strip(),
        "args_schema": ListInvoicesParameters,
        "actions": {"invoices": {"list": True}},
        "execute": list_invoices,
    },
    {
        "method": "get_invoice",
        "name": "Get Invoice",
        "description": GET_INVOICE_PROMPT.strip(),
        "args_schema": GetInvoiceParameters,
        "actions": {"invoices": {"get": True}},
        "execute": get_invoice,
    },
    {
        "method": "send_invoice",
        "name": "Send Invoice",
        "description": SEND_INVOICE_PROMPT.strip(),
        "args_schema": SendInvoiceParameters,
        "actions": {"invoices": {"send": True}},
        "execute": send_invoice,
    },
    {
        "method": "send_invoice_reminder",
        "name": "Send Invoice Reminder",
        "description": SEND_INVOICE_REMINDER_PROMPT.strip(),
        "args_schema": SendInvoiceReminderParameters,
        "actions": {"invoices": {"sendReminder": True}},
        "execute": send_invoice_reminder,
    },
    {
        "method": "cancel_sent_invoice",
        "name": "Cancel Sent Invoice",
        "description": CANCEL_SENT_INVOICE_PROMPT.strip(),
        "args_schema": CancelSentInvoiceParameters,
        "actions": {"invoices": {"cancel": True}},
        "execute": cancel_sent_invoice,
    },
    {
        "method": "generate_invoice_qr_code",
        "name": "Generate Invoice QR Code",
        "description": GENERATE_INVOICE_QRCODE_PROMPT.strip(),
        "args_schema": GenerateInvoiceQrCodeParameters,
        "actions": {"invoices": {"generateQRC": True}},
        "execute": generate_invoice_qrcode,
    }
   
]
