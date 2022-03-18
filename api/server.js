const express = require('express');
const cors = require('cors');
const { json } = require('body-parser');

const app = express();

const data = {
  count: 8,
  next: null,
  previous: null,
  facets: {
    _filter_author: {
      doc_count: 8,
      author: {
        doc_count_error_upper_bound: 0,
        sum_other_doc_count: 0,
        buckets: [
          {
            key: 'Magistrate KE',
            doc_count: 5
          },
          {
            key: 'Court SA',
            doc_count: 2
          },
          {
            key: 'Court TZ',
            doc_count: 1
          }
        ]
      }
    },
    _filter_country: {
      doc_count: 8,
      country: {
        doc_count_error_upper_bound: 0,
        sum_other_doc_count: 0,
        buckets: [
          {
            key: 'Kenya',
            doc_count: 5
          },
          {
            key: 'South Africa',
            doc_count: 2
          },
          {
            key: 'Tanzania',
            doc_count: 1
          }
        ]
      }
    },
    _filter_date: {
      doc_count: 8,
      date: {
        buckets: [
          {
            key_as_string: '2021-01-01T00:00:00.000Z',
            key: 1609459200000,
            doc_count: 2
          },
          {
            key_as_string: '2022-01-01T00:00:00.000Z',
            key: 1640995200000,
            doc_count: 6
          }
        ]
      }
    },
    _filter_matter_type: {
      doc_count: 8,
      matter_type: {
        doc_count_error_upper_bound: 0,
        sum_other_doc_count: 0,
        buckets: [
          {
            key: 'Treaty',
            doc_count: 4
          },
          {
            key: 'Case Law',
            doc_count: 2
          },
          {
            key: 'Communication',
            doc_count: 2
          }
        ]
      }
    }
  },
  results: [
    {
      title: 'Animi dolorum quis iure temporibus laboris et aspernatur deserunt voluptatem',
      date: '2022-03-17',
      author: 'Magistrate KE',
      country: 'Kenya',
      citation: 'Deleniti culpa minim proident est vero nihil',
      matter_type: 'Treaty',
      document_content: 'Dolor et reiciendis'
    },
    {
      title: 'Aperiam occaecat quis elit lorem similique irure fugiat proident illo reprehenderit quae cupidatat sint dolore dignissimos earum sit voluptatem',
      date: '2022-03-05',
      author: 'Magistrate KE',
      country: 'Kenya',
      citation: 'Quidem sed et quod nesciunt ullamco quae mollitia numquam nisi quis amet quaerat blanditiis eum similique',
      matter_type: 'Treaty',
      document_content: 'Et excepturi digniss'
    },
    {
      title: 'Est praesentium aut ut blanditiis qui nostrum voluptatum quis ipsum iure eum nisi pariatur Reiciendis ut nulla est',
      date: '2022-03-17',
      author: 'Magistrate KE',
      country: 'Kenya',
      citation: 'Saepe non suscipit animi minus voluptate sint ut nostrum ducimus qui aut id dolor repellendus',
      matter_type: 'Treaty',
      document_content: 'Eveniet sunt et est'
    },
    {
      title: 'Doloribus qui anim adipisci dolores et dolor at provident fuga Architecto non voluptas sint itaque in consequuntur enim',
      date: '2021-12-08',
      author: 'Court SA',
      country: 'South Africa',
      citation: 'Voluptas doloremque perspiciatis sed ex dolorem aut possimus vero assumenda',
      matter_type: 'Case Law',
      document_content: 'Maiores qui odio inc'
    },
    {
      title: 'Voluptatem officiis quis officia dignissimos sint quibusdam qui qui sed non qui adipisci et aliquip est architecto fuga Animi',
      date: '2022-03-17',
      author: 'Court SA',
      country: 'South Africa',
      citation: 'Nulla excepturi dolore irure ea est necessitatibus possimus irure occaecat ea explicabo Ut cupiditate',
      matter_type: 'Case Law',
      document_content: 'Temporibus ex volupt'
    },
    {
      title: 'Doloribus quae deleniti amet dolor ad',
      date: '2022-03-15',
      author: 'Magistrate KE',
      country: 'Kenya',
      citation: 'Et illo perferendis velit dolorem dicta recusandae Dolore ea quisquam enim sunt',
      matter_type: 'Communication',
      document_content: 'Officia commodo qui'
    },
    {
      title: 'Excepturi reprehenderit quis cillum consequatur Odio nihil qui ullam ducimus laboris autem est eos fugit magnam maiores non hic dolor',
      date: '2022-03-17',
      author: 'Magistrate KE',
      country: 'Kenya',
      citation: 'Neque duis ea magni in tempor vero sit neque et hic quasi rerum possimus corporis aut molestiae',
      matter_type: 'Treaty',
      document_content: 'Laborum Ut inventor'
    },
    {
      title: 'Ex ut nisi tempore harum qui non molestiae',
      date: '2021-09-15',
      author: 'Court TZ',
      country: 'Tanzania',
      citation: 'Rem atque amet pariatur Recusandae Et iure expedita adipisicing natus beatae ab ea ad obcaecati itaque illum amet enim aut',
      matter_type: 'Communication',
      document_content: 'Est vero neque modi'
    }
  ]
};

app.use(cors());
app.use(json());

app.get('/api/search', (req, res) => res.send(data));

const PORT = 7000;

app.listen(PORT, console.log(`Server running on port ${PORT}`));
