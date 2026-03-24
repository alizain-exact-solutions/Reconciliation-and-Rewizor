**February Agenda for AI team**

**CEO’s Requirements**  
 **Prepared by: Ariba Ali (Technical Project Coordinator)**

 **1\) Under Financial Agent:**

 **A. Invoice & Cost Management**

* **Goal:** Track operating costs and input VAT from supplier invoices.  
* **Features:**

  1\.      Upload/scan invoice (PDF/image) → AI extracts: Invoice \#, Supplier, Date, Net, VAT, Gross, Currency.  
   \- The goal here is to remove manual invoice handling and give you a clean view of real operating costs and input VAT

  2\.      Auto-convert foreign currency to PLN using NBP exchange rates (based on invoice date).  
   \- Foreign currency invoices are converted into PLN automatically using official NBP rates based on invoice date, so VAT reporting stays compliant

  3\.      Categorize invoices: **Operating Cost** (include) vs **Inventory Purchase** (exclude from cost report).  
   \- We separate operating costs from inventory purchases so cost reports are not inflated and decision making stays accurate

  4\.      Store all invoices with a link to original file.

  5\.      All invoices and related documents will also be stored in Google  \- Cloud Storage as a secondary secure repository, ensuring availability, backup, and audit readiness.e

**Value added:** This reduces accounting effort, avoids human errors, and gives you reliable cost visibility at any time.

Please research **on [https://www.saldeosmart.pl/](https://www.saldeosmart.pl/) need to implement its features**

 **SaldeoSMART** helps with:

**✔ OCR & Automatic Invoice Reading** → Recognizes and extracts data from invoices (supplier, amounts, dates, line items). Users upload PDF/image; OCR parses content into structured fields. Removes manual typing, speeds up accounting entry. 

 **✔ Automatic bank feed \+ reconciliation** → supports matching bank transactions to invoices.  
 **✔ AI payment verification** → simplifies tracking paid vs unpaid.

**✔ Automated Reconciliation** → Matches invoices to bank transactions. AI compares amounts, dates, partners automatically.

 **✔ PDF/e-archive of documents** → supports audit and reporting.

**✔ Sales Invoicing & Billing** → Built-in module to create and issue invoices.

**✔ Bank Account Sync & Transaction Import** → Connects business bank accounts. API or secure sync pulls transaction data regularly. Eliminates manual bank imports and speeds reconciliation. 

**✔ Electronic Document Workflow** → Digital circulation of accounting paperwork. Documents are routed and approved online, with history and status tracking.

**✔ KSeF (E-Invoice National System) Integration** →  Direct integration with Poland’s government e-invoicing platform. Send and retrieve e-invoices securely without manual portal work. Compliance with government standards \+ error protection. 

 ![][image1]

**B. Bank Reconciliation & VAT Validation**

* **Goal:** Match bank payments to invoices, calculate VAT correctly.  
* **Features:**

  1\.      Import bank statements (CSV/MT940).  
   \- This part ensures that what we paid from the bank actually matches valid invoices

  2\.      Match transactions to invoices (by invoice number, amount, supplier).  
   \- Bank statements are imported and matched automatically with invoices using amount, supplier, and invoice number

  3\.      **Exclude from VAT calculation:** FX conversions, bank fees, internal transfers, salaries, tax payments (ZUS), customer payments.  
   \- The system excludes non VAT items like salaries, bank charges, ZUS, and FX conversions so VAT calculations stay clean

  4\.      Show “missing invoice” alerts for payments without invoices.  
   \- If a payment exists without an invoice, the system flags it immediately instead of discovering it during audits

  5\.      Export reconciled data and reports in both Excel and PDF formats for audits, compliance, and management review.

**Value added**: This protects the company from VAT mistakes, penalties, and missing documentation.

 

**2\) People Force**

 **C. Follow-up Task System**

* **Goal:** Ensure recurring and overdue tasks are always visible until completed.  
* **Features:**

  1\.      Create tasks with repeat rules: daily, weekly, monthly.

  2\.      Overdue tasks stay in weekly view until done.

  3\.      If the task is not completed, Automatic email/notification reminders to assignee and the assigned person.  
   \- Automatic reminders push accountability without manual follow ups

  4\.      Task completion directly affects employee KPIs, so performance is measurable

**Value added:** This builds discipline, transparency, and ownership without micromanagement.

**D. Employee & Department KPI Dashboard**

* **Goal:** Monitor attendance and productivity per department.  
* **Features:**

  1\.      **Polish team:** Attendance tracking highlights late arrivals, breaks, and absences clearly.

  2\.      **Warehouse:** Each department has clear measurable output like packing count, testing units, or RMA resolution.

* Warehouse quality checks  
* Packing accuracy validation  
* Correct product selection  
* Correct grading confirmation  
* Error rate per packer

  3\.      **Testing:** Units tested per day.

  4\.      **RMA:** Received vs resolved, backlog aging.

  5\.      Dashboards with charts, export to Excel/PDF.

  \- You can export reports anytime for reviews or meetings

  6\.  **Role based performance evaluation**:  
   \- Each employee is evaluated based on their assigned role such as packing, grading, testing, or RMA.  
   \- Performance metrics reflect whether tasks were completed correctly, not just completed.

  7\.      AI summaries: “Last week’s productivity down 10% due to…”

  8\.       Employee profile dashboard: When opening an employee, display a dedicated dashboard showing joining date, attendance history, absent days, completed tasks, overdue tasks, and overall performance score or trend.

## **3\. February Mandatory Execution Rules**

1. **Ownership and completion**  
   Every requirement submitted by team leads or departments must be fully implemented, fully tested, and deployed end to end. Partial delivery is not acceptable.  
   If any requirement has a blocker, dependency, or is identified as out of scope, it must be reported immediately to avoid miscommunication, delays, or last minute surprises later.  
2. **Chatbot implementation**  
    General chatbot requirements provided by Ariba must be fully implemented.

3. **Data accuracy enforcement**  
    All dashboard numbers, KPIs, and statistics must be fully accurate and verified with relevant teams and stakeholders before sign off.

4. **Cross department feedback loop**  
    Feedback must be collected from every department.  
    Any identified issue or bug must be fixed immediately and not deferred.

5. **Marketing AI research**  
   Research on Artisan for ExactFlow marketing implementation is included in the February agenda. (https://www.artisan.co/)  
   Modules and use cases must be identified in collaboration with the marketing team.  
   Implementation will begin in March after final approval.

6. **Team training**  
    Training sessions must be conducted for the entire Polish team.  
    Employees must be instructed clearly on how to use the relevant AI agents and dashboards.