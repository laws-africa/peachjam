const express = require('express');
const cors = require('cors');
const { json } = require('body-parser');

const app = express();

const data = {
  count: 466,
  next: 'https://public.gazettes.africa/api/search/?facet=jurisdiction_name&facet=year&facet=publication&facet=sub_publication&ordering=-score&page=2&search=russia',
  previous: null,
  facets: {
    _filter_publication: {
      doc_count: 466,
      publication: {
        doc_count_error_upper_bound: 0,
        sum_other_doc_count: 0,
        buckets: [
          {
            key: 'Government Gazette',
            doc_count: 420
          },
          {
            key: 'Provincial Gazette',
            doc_count: 44
          },
          {
            key: 'Journal Officiel',
            doc_count: 1
          },
          {
            key: 'Official Journal',
            doc_count: 1
          }
        ]
      }
    }
  },
  results: [
    {
      name: 'Seychelles Government Gazette dated 2021-03-09 number 21',
      publication: 'Government Gazette',
      date: '2021-03-09',
      year: 2021,
      download_url: 'https://archive.gazettes.africa/archive/sc/2021/sc-government-gazette-dated-2021-03-09-no-21.pdf',
      pages: [
        {
          page_num: 2,
          highlight: {
            'pages.body': [
              'Gamaleya RCEM of the\nMinistry of Health of <mark>Russia</mark>\n(Medgamal Branch of FSBI N.F.,',
              'Gamaleya RCEM of Ministry of\nHealth of <mark>Russia</mark>), <mark>Russia</mark> (Finished\nDosage Form Manufacturing'
            ]
          }
        }
      ]
    }
  ]
};

app.use(cors());
app.use(json());

app.get('/api/search', (req, res) => res.send(data));

const PORT = 7000;

app.listen(PORT, console.log(`Server running on port ${PORT}`));
