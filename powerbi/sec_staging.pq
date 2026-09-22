// sec_staging.pq  -  Power Query (M) staging step for the raw SEC extract.
// Excel for Mac: Data > Get Data (Power Query) > Blank query > Advanced Editor, paste,
// then change FilePath. Power BI Desktop: Home > Transform data > New source > Blank query.
//
// What it does: types the columns, keeps 10-Q/10-K rows, maps XBRL concepts to P&L
// lines, and keeps the latest-filed value for each ticker/line/period (the same
// de-duplication as sql/01_quarters.sql). The quarter derivation (Q4 = FY - 9-month YTD)
// stays in SQL, where it is testable.
let
    FilePath = "/Users/<you>/Documents/fpa-variance/data/raw/sec_hd_low_income_statement.csv",
    Source   = Csv.Document(File.Contents(FilePath), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers  = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Headers, {
                   {"ticker", type text}, {"concept", type text}, {"fy", Int64.Type}, {"fp", type text},
                   {"form", type text}, {"start", type date}, {"end", type date}, {"days", Int64.Type},
                   {"val", type number}, {"filed", type date}}),
    Forms    = Table.SelectRows(Typed, each [form] = "10-Q" or [form] = "10-K"),
    LineMap  = #table({"concept", "line"}, {
                   {"RevenueFromContractWithCustomerExcludingAssessedTax", "revenue"},
                   {"CostOfRevenue", "cost_of_sales"},
                   {"CostOfGoodsAndServicesSold", "cost_of_sales"},
                   {"GrossProfit", "gross_profit"},
                   {"SellingGeneralAndAdministrativeExpense", "sga"},
                   {"DepreciationAndAmortization", "da"},
                   {"OperatingIncomeLoss", "operating_income"},
                   {"NetIncomeLoss", "net_income"}}),
    Joined   = Table.NestedJoin(Forms, {"concept"}, LineMap, {"concept"}, "m", JoinKind.Inner),
    WithLine = Table.ExpandTableColumn(Joined, "m", {"line"}),
    Sorted   = Table.Buffer(Table.Sort(WithLine, {{"filed", Order.Descending}})),
    Latest   = Table.Distinct(Sorted, {"ticker", "line", "start", "end"}),
    Result   = Table.SelectColumns(Latest, {"ticker", "line", "start", "end", "days", "val", "filed"})
in
    Result
