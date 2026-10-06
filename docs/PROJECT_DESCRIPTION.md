# Garuka: A USSD Early-Warning and Follow-Up System for School Dropout

*(Garuka means "come back" in Kinyarwanda. It is a working name.)*

---

## 1. What It Is

Garuka turns a missed school day into a fast, tracked response. A teacher records who is absent by phone. The parent hears about it the same day. If the absences continue, a paid local youth mentor visits the home. If the family faces a barrier the school can't solve, the case moves up to the sector education officer.

---

## 2. Why the Gap Exists

SDMS is web-based and works through logins for school staff, approved by district authorities. MINEDUC has also planned a dashboard showing every student's attendance status. Rural internet use, by contrast, is below 20%, and dropout rose between 2019 and 2021. My reading, which you should test with a head teacher, is that the data exists but the loop from "child absent" to "someone acts" is weak. Garuka closes that loop.

---

## 3. The Journey, Step by Step

### Setup (Once Per School)
- The head teacher registers the school. Class lists are imported from SDMS or a CSV using each student's unique ID.
- Each parent's phone number is linked to their child, with consent recorded.

### Every School Day
- **Teacher marks absences by USSD**: To keep it under a minute, the teacher enters only the absent students, not the whole class. They pick the class and then enter student numbers.
- **Parent notified the same day**: The parent gets an SMS saying their child was marked absent and can dial the code to give a reason (sick, farm work, fees or uniform, distance, other). These reason codes are valuable data because they show why children stop attending.

### When Absences Continue (Thresholds to be Tuned in the Pilot)
- **Three consecutive days or five in a month**: The child is flagged on the head teacher's dashboard, and a mentor is assigned.
- **Mentor visits within three school days**: The mentor checks in by USSD with the case code, and the parent confirms the visit with an SMS code so visits can't be faked. The mentor logs an outcome: returned to school, plan agreed, needs help, or moved away.
- **Escalation to the Sector Education Officer (SEO)**: This happens after about ten absences, or when the mentor reports a barrier beyond their reach, such as fees, hunger, disability or a distant school. The SEO coordinates with cell and village leaders and social services.
- **District level**: The district director of education sees monthly unresolved cases and trends by sector.
- **Closure**: A case closes only when the child is back for a set number of weeks, and it reopens if absences resume.

### Risk Scoring
Risk scoring should also consider Primary 5 and 6 pupils, over-age children and repeaters. Earlier research links dropout to age and repetition, and it peaks at the primary-to-secondary transition.

---

## 4. Who Sees What

| Role | Channel | Sees / Does |
| :--- | :--- | :--- |
| **Teacher** | USSD | Marks absences, sees their class flags |
| **Parent** | USSD + SMS | Gets alerts, gives absence reasons, views attendance |
| **Mentor** | USSD | Gets assigned cases, logs visits and outcomes |
| **Head Teacher** | Dashboard | At-risk list, case status, class trends |
| **Sector Education Officer** | Dashboard | Escalated cases, school comparison, mentor performance |
| **District Director** | Dashboard | Sector trends, unresolved cases, reports |
| **Platform Admin** | Dashboard | Schools, users, thresholds, audit logs, fraud checks |

---

## 5. Technical Outline (Fits Your Stack)

- **USSD gateway**: Through an aggregator or telecom partner, with a RURA-approved short code. Check costs and the approval process early. Since January 2026 approved codes must work across all networks, which helps you.
- **Backend**: FastAPI with PostgreSQL. Redis holds USSD session state. A rules engine handles thresholds and escalation, and a scheduler sends reminders and runs escalation checks.
- **Dashboard**: Next.js with role-based access.
- **Core tables**: Schools, students, guardians, attendance records, absence reasons, cases, mentor visits, escalations and audit logs.
- **SDMS link**: Start with CSV import. Ask MINEDUC about API access later.

---

## 6. Benefits

- **Families**: Fast contact, and a route to help when the barrier is money, distance or health.
- **Schools**: Less time chasing absentees and clearer records.
- **Government**: Faster action on dropout, plus data on why children leave, by sector.
- **Jobs**: Paid attendance mentors, catch-up tutors and local field coordinators.
- **Funding fit**: This aligns with the national goal of reducing dropout, which makes UNICEF, NGOs or district programs plausible funders.

---

## 7. Risks & Mitigations

| Risk | Why It Matters | Mitigation |
| :--- | :--- | :--- |
| **Teachers stop logging** | Data goes stale, alerts become useless | Exception-only entry; sector officers monitor completeness |
| **Duplicate work with SDMS** | Teachers resent double entry | Integrate and import from SDMS; don't replace it |
| **Child data privacy** | Minors' data is sensitive | Consent, minimum data, role-based access, audit logs; check Rwanda's data protection law with a legal adviser |
| **Mentor quality or fraud** | Fake visits, poor conduct | Parent SMS confirmation, mentor training, spot checks |
| **Stigma for flagged families** | Shame can push families away | Supportive messages, no public lists |
| **USSD limits** | Short screens, session timeouts | Simple menus, resumable steps |
| **Funding for mentors** | Jobs collapse if unpaid | Secure a pilot funder before hiring |
| **Overlap with existing programs** | Could look like duplication | Partner with the Zero Out-of-School Children consortium |

---

## 8. The Hardest Part

The code is the easy part. There are two harder problems:
1. **Consistent daily use by teachers**, without adding to their workload.
2. **Making the follow-up real and paid for**. Mentors are what make this more than an SMS tool, so you need a funding source and quality control for them.

A close third is **getting MINEDUC and district buy-in**. Without it, the system can't connect to official student records.
