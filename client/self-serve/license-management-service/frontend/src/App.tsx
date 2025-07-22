import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import Licenses from './pages/Licenses'
import Usage from './pages/Usage'
import Validation from './pages/Validation'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/customers" element={<Customers />} />
        <Route path="/licenses" element={<Licenses />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/validation" element={<Validation />} />
      </Routes>
    </Layout>
  )
}

export default App