# Demo Script

1. Open frontend at `http://localhost:5178`
2. Open gateway Swagger at `http://localhost:8500/docs`
3. Call `POST /workflow/process-paper` with a new preprint payload
4. Show indexed paper in `GET /dashboard/{paper_id}/{user_id}`
5. Show recommendation list and quality KPI cards (`NDCG@10`, `Precision@10`)
6. Show citation graph and coauthor graph sections
7. Call `POST /notify/citation` to simulate citation alert
8. Show alert history in dashboard notifications panel
9. Show ORCID link and BibTeX/RIS export endpoints in `user-service`
