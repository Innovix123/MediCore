"""Import every model so SQLAlchemy knows about all tables."""
from app.models.analytics import Feedback, Reminder, SearchLog, StockAlertSubscription  # noqa: F401
from app.models.customer import Customer, FamilyMember, PatientAllergy, PatientMedication  # noqa: F401
from app.models.finance import CreditLedger, Expense, LoyaltyPoint, Offer  # noqa: F401
from app.models.inventory_ops import Branch, StockTransfer, StockWriteoff, SupplierReturn  # noqa: F401
from app.models.medicine import Batch, Medicine  # noqa: F401
from app.models.order import Delivery, Order, OrderItem, Reservation  # noqa: F401
from app.models.pharmacy import Pharmacy  # noqa: F401
from app.models.prescription import (CounselingNote, Doctor, DrugInteraction, Prescription,  # noqa: F401
                                     PrescriptionUpload)
from app.models.sales import Invoice, InvoiceItem, Payment, SaleReturn  # noqa: F401
from app.models.staff import Permission, Role, Shift, User  # noqa: F401
from app.models.supplier import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, Supplier  # noqa: F401
from app.models.audit import AuditLog, ConsentRecord  # noqa: F401  (registers audit listeners)
