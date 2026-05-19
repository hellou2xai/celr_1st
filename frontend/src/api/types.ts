// Response shapes for the backend JSON API. Mirrors the analytics layer.

export interface DashboardSummary {
  open_po_count: number;
  open_line_count: number;
  open_po_value: number;
  cancel_value: number;
  cancel_lines: number;
  rtv_value: number;
  rtv_in_window_value: number;
  recent_stockouts: number;
  risk_rollup: Record<string, { lines: number; value: number }>;
  top_cancel_suppliers: Array<{
    SupplierName: string;
    CancelLines: number;
    ReduceLines: number;
    RecoverableValue: number;
  }>;
}

export interface OpenPOLine {
  PONumber: string;
  PODate: string;
  SupplierName: string;
  UPC: string;
  Description: string;
  Department: string;
  QtyOrdered: number;
  QtyReceived: number;
  QtyOpen: number;
  UnitCost: number;
  LineValue: number;
  OnHand: number;
  AvgMonthlySales: number;
  CurrentMoS: number | null;
  ProjectedMoS: number | null;
  Risk: string;
  Action: "CANCEL" | "REDUCE" | "KEEP";
  Reason?: string;
}

export interface OpenPOsResponse {
  summary: {
    line_count: number;
    total_value: number;
    cancel_value: number;
    reduce_value: number;
    recoverable: number;
  };
  by_supplier: Array<{
    SupplierName: string;
    Lines: number;
    Value: number;
    CancelLines: number;
    ReduceLines: number;
    RecoverableValue: number;
  }>;
  lines: OpenPOLine[];
}

export interface ItemDrillResponse {
  found: boolean;
  identifier?: string;
  resolved_by?: string;
  alt_matches?: Array<{ UPC: string; Description: string }>;
  history_months: number;
  item?: {
    ID: number;
    UPC: string;
    Description: string;
    Department: string;
    Category: string;
    OnHand: number;
    OpenPOQty: number;
    AvgMonthlySales: number;
    CurrentMoS: number | null;
    DaysToStockout: number | null;
    Cost: number;
    Price: number;
    Risk: string;
  };
  summary?: {
    transaction_count: number;
    units_sold_abs: number;
    units_received: number;
    last_sale_in_window: string | null;
    last_receive_in_window: string | null;
  };
  open_pos?: Array<{
    PONumber: string;
    PODate: string;
    SupplierName: string;
    QtyOrdered: number;
    QtyReceived: number;
    QtyOpen: number;
    UnitCost: number;
    LineTotal: number;
  }>;
  transactions?: Array<{
    TxnDate: string;
    TxnType: string;
    QtyImpact: number;
    UnitPrice: number;
    LineTotal: number;
    RunningQty: number;
    Reference: string;
    PONumber?: string;
    SupplierName?: string;
    InvoiceNumber?: string;
    InvoiceID?: number;
  }>;
}

export interface TxnDrillResponse {
  found: boolean;
  kind?: "transaction" | "itl";
  reference?: string;
  error?: string;
  type?: string;
  event_time?: string;
  total_qty?: number;
  total_value?: number;
  source_id?: number;
  header?: {
    TransactionNumber: number;
    TxnDate: string;
    SubTotal: number;
    SalesTax: number;
    Total: number;
    Comment?: string;
  };
  lines?: Array<{
    ID?: number;
    UPC: string;
    Description: string;
    Department?: string;
    Quantity: number;
    Price?: number;
    Cost?: number;
    LineTotal: number;
  }>;
}

export interface StockoutRow {
  UPC: string;
  Description: string;
  Department: string;
  Category: string;
  SupplierName: string;
  OnHand: number;
  OpenPOQty: number;
  AvgMonthlySales: number;
  DaysSinceLastSale: number;
  EstLostSalesPerWeek: number;
  Risk: string;
  Action: string;
}

export interface RTVRow {
  UPC: string;
  Description: string;
  SupplierName: string;
  OnHand: number;
  Cost: number;
  InventoryValue: number;
  LastReceived: string;
  DaysInStore: number;
  InReturnWindow: boolean;
}
