import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import Licenses from './pages/Licenses'
import Usage from './pages/Usage'
import Validation from './pages/Validation'

// Simplified Customer Portal Components
import SelectTier from './pages/customer/SelectTier'
import SimpleDashboard from './pages/customer/SimpleDashboard'

function App() {
  return (
    <Routes>
      {/* Admin Routes */}
      <Route path="/admin/*" element={
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/licenses" element={<Licenses />} />
            <Route path="/usage" element={<Usage />} />
            <Route path="/validation" element={<Validation />} />
          </Routes>
        </Layout>
      } />
      
      {/* Simplified Customer Portal Routes */}
      <Route path="/customer" element={<SimpleDashboard />} />
      <Route path="/customer/select-tier" element={<SelectTier />} />
      
      {/* Default redirect to admin */}
      <Route path="/" element={<Dashboard />} />
    </Routes>
  )
}

export default App