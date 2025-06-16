# N8N Company Research & Personalized Email Generator Workflow

## Overview

This comprehensive n8n workflow automates the entire process of company research and personalized cold email generation. It integrates with Notion, Hunter.io, Google Custom Search, LinkedIn, and Gmail to create a fully automated outreach system that researches companies, finds key contacts, conducts deep personal research, and generates highly personalized email drafts.

## Workflow Architecture

### Workflow Summary
- **Trigger**: Automated schedule (Monday & Thursday, 9:00 AM)
- **Input Source**: Notion "Shopify DB" database
- **Output**: Personalized Gmail drafts with research documentation
- **Processing**: Company-by-company research with comprehensive contact discovery
- **Notification**: Discord summary reports

### Key Features
- ✅ **Automated Scheduling**: Runs twice weekly
- ✅ **Notion Integration**: Reads companies and creates research pages
- ✅ **Contact Discovery**: Uses Hunter.io for email finding
- ✅ **Deep Research**: LinkedIn profiles and web search
- ✅ **Personalized Emails**: AI-generated with personal touches
- ✅ **Quality Control**: Email validation and filtering
- ✅ **Gmail Integration**: Creates drafts (no accidental sending)
- ✅ **Progress Tracking**: Notion sub-pages with detailed research
- ✅ **Rate Limiting**: Respects API limits and prevents blocks

## Node-by-Node Breakdown

### Phase 1: Trigger & Initialization

#### Node 1: Schedule Trigger - Mon/Thu 9AM
- **Type**: Schedule Trigger
- **Schedule**: Monday and Thursday at 9:00 AM
- **Purpose**: Initiates the workflow automatically twice per week
- **Configuration**:
  - Weekdays: [1, 4] (Monday, Thursday)
  - Hour interval: 1 (runs once per day when triggered)

#### Node 2: Get Companies from Notion
- **Type**: Notion Node
- **Operation**: Database Page Get Many
- **Database ID**: `1ff81fd0-43ce-8040-9e29-fbc2cca2056f` (Shopify DB)
- **Configuration**:
  - Return All: `true`
  - No filters (processes all companies)
- **Output**: Array of company records with properties

#### Node 3: Loop Over Companies
- **Type**: Split In Batches Node
- **Configuration**:
  - Batch Size: 1 (process one company at a time)
  - Reset: `true` (reset position if input changes)
- **Purpose**: Prevents API rate limits and allows individual company processing

### Phase 2: Sub-Page Management

#### Node 4: Check for Existing Sub-Page
- **Type**: Notion Node
- **Operation**: Database Page Get All
- **Purpose**: Check if company already has a research sub-page
- **Filter**: Search by Store Name (company name)
- **Error Handling**: Continue on fail

#### Node 5: IF - Page Exists Check
- **Type**: IF Node
- **Condition**: Check if results array is empty
- **Logic**:
  - `True`: No existing page → Create new page
  - `False`: Page exists → Use existing page

#### Node 6: Create Company Sub-Page
- **Type**: Notion Node
- **Operation**: Page Create
- **Purpose**: Create research sub-page for new companies
- **Properties**:
  - Title: `{Company Name} - Research`
  - Parent: Main Shopify DB page

#### Node 7: Merge Page Data
- **Type**: Merge Node
- **Mode**: Combine All
- **Purpose**: Unify page data whether newly created or existing

### Phase 3: Contact Discovery

#### Node 8: Build Search Query
- **Type**: Code Node
- **Purpose**: Prepare search parameters and target roles
- **Logic**:
  - Extract company domain from website
  - Define target titles (CEO, CTO, CMO, etc.)
  - Construct domain if not provided
- **Output**: Structured search parameters

**Target Roles**:
- CEO, CTO, CMO, CFO
- Founder, Co-founder
- Chief Data Officer
- Head of Ecommerce, Head of Analytics
- Director of Digital, Data Director
- VP Engineering

#### Node 9: Hunter.io Domain Search
- **Type**: HTTP Request Node
- **API**: Hunter.io Domain Search
- **Parameters**:
  - Domain: Extracted from company data
  - Limit: 100 contacts
  - Type: Personal emails
  - Seniority: Senior, Executive
- **Purpose**: Find email patterns and senior contacts

#### Node 10: Process Domain Search Results
- **Type**: Code Node
- **Purpose**: Filter and process Hunter.io results
- **Logic**:
  - Filter contacts by target roles
  - Create contact objects with confidence scores
  - Determine if additional searches needed

#### Node 11: IF - Enough Contacts Found
- **Type**: IF Node
- **Condition**: Check if ≥3 quality contacts found
- **Logic**:
  - `True`: Proceed with existing contacts
  - `False`: Perform additional email finder searches

#### Node 12: Hunter.io Find Specific Contacts
- **Type**: HTTP Request Node
- **API**: Hunter.io Email Finder
- **Purpose**: Find specific contacts by role when domain search insufficient
- **Parameters**: Domain, company name, specific titles

#### Node 13: Filter Quality Contacts
- **Type**: Code Node
- **Purpose**: Combine and filter all contact results
- **Quality Criteria**:
  - Email confidence > 70%
  - Has first and last name
  - Remove duplicates
  - Limit to top 10 contacts per company
- **Sorting**: By confidence score (highest first)

### Phase 4: Deep Research

#### Node 14: LinkedIn Profile Research
- **Type**: HTTP Request Node
- **API**: LinkedIn API
- **Purpose**: Extract professional background
- **Data Extracted**:
  - Current position and tenure
  - Previous companies
  - Education background
  - Skills and endorsements
- **Error Handling**: Continue on fail (LinkedIn API restrictions)

#### Node 15: Web Search for Personal Details
- **Type**: HTTP Request Node
- **API**: Google Custom Search API
- **Purpose**: Find personal achievements and mentions
- **Search Queries**:
  - `"{Name}" "{Company}" (interview OR speaker OR award OR podcast OR quote)`
- **Results**: Up to 5 relevant articles/mentions per contact

#### Node 16: Company News Search
- **Type**: HTTP Request Node
- **API**: Google Custom Search API
- **Purpose**: Find recent company developments
- **Search Query**:
  - `"{Company}" (news OR announcement OR product OR launch OR funding) after:{3_months_ago}`
- **Results**: Recent company news for contextualization

#### Node 17: Aggregate Research Data
- **Type**: Code Node
- **Purpose**: Combine all research into structured format
- **Data Structure**:
```javascript
{
  name: "Contact Name",
  email: "email@company.com",
  position: "CEO",
  company: "Company Name",
  personal_details: {
    career_highlights: [...],
    education: [...],
    achievements: [...],
    unique_hooks: [...]
  },
  company_context: {
    recent_news: [...],
    pain_points: [...]
  }
}
```

### Phase 5: Email Generation

#### Node 18: Generate Personalized Email
- **Type**: Code Node
- **Purpose**: Create highly personalized email content
- **Personalization Logic**:
  1. Select most relevant personal detail for opening
  2. Reference specific company achievement/news
  3. Connect their challenges to Ceneca solution
  4. Keep under 200 words

**Email Template Structure**:
```
Hi {FirstName},

{Personalized opening based on research}

{Company-specific observation about data challenges}

We're building Ceneca - an on-prem AI analytics agent that plugs directly into your databases (no data ever leaves your network). It creates bespoke AI data analysts that understand your specific business context.

I'd love to understand the gaps or frustrations in {Company}'s current analytics workflows so we can tailor our solution for teams like yours.

Do you have 10 minutes next week for a quick call? I want to build something that would genuinely help {Company} make better data-driven decisions.

Best,
Hardik
Founder & CEO, Ceneca
ceneca.ai
```

#### Node 19: Email Quality Check
- **Type**: IF Node
- **Purpose**: Validate email quality before sending
- **Quality Criteria**:
  - Word count < 200
  - Contains personalized opening
  - Mentions specific company detail
  - No generic phrases
  - Proper formatting
- **Action**: Only proceed with high-quality emails

### Phase 6: Documentation & Output

#### Node 20: Update Notion Sub-Page
- **Type**: Notion Node
- **Operation**: Append Block Children
- **Purpose**: Document research and email drafts
- **Content Added**:
  - Contact details with confidence scores
  - Research summary (achievements, career highlights)
  - Email draft preview
  - Company news references
  - Timestamp and source attribution

#### Node 21: Create Gmail Draft
- **Type**: Gmail Node
- **Operation**: Create Draft
- **Purpose**: Create email drafts (NOT send)
- **Configuration**:
  - To: Contact email
  - Subject: Dynamically generated
  - Body: Personalized email content
  - Labels: ["Ceneca Outreach", Company Name]
- **Safety**: Creates drafts only, no automatic sending

#### Node 22: Create Summary Report
- **Type**: Code Node
- **Purpose**: Generate workflow execution summary
- **Metrics Tracked**:
  - Companies processed
  - Total contacts found
  - Successful emails created
  - Failed emails (with reasons)
  - Processing timestamp

#### Node 23: Discord Notification
- **Type**: Discord Node
- **Purpose**: Send summary to team channel
- **Format**: Markdown with key statistics
- **Content**:
  - Company processed
  - Contact count and success rate
  - Individual contact results
  - Workflow completion time

#### Node 24: Wait - Rate Limiting
- **Type**: Wait Node
- **Duration**: 2 seconds
- **Purpose**: Prevent API rate limiting between companies
- **Placement**: Between companies in the loop

### Phase 7: Error Handling & Loop Management

#### Error Handling Strategy
- **Continue on Fail**: All API nodes have this enabled
- **Fallback Logic**: Missing data handled gracefully
- **Rate Limiting**: Built-in delays between API calls
- **Quality Control**: Multiple validation checkpoints

#### Loop Management
- **Batch Processing**: One company at a time
- **Progress Tracking**: Each company creates individual sub-page
- **State Management**: Loop tracks completion status
- **Resource Management**: Automatic cleanup between iterations

## Required Credentials & APIs

### 1. Notion API
- **Purpose**: Read companies, create/update research pages
- **Setup**: Create integration in Notion workspace
- **Permissions**: Read/write access to Shopify DB
- **Database ID**: `1ff81fd0-43ce-8040-9e29-fbc2cca2056f`

### 2. Hunter.io API
- **Purpose**: Email discovery and verification
- **Endpoints Used**:
  - Domain Search: Find all emails for a domain
  - Email Finder: Find specific person's email
- **Rate Limits**: 100 requests/month (free tier)
- **Required Data**: Company domain

### 3. Google Custom Search API
- **Purpose**: Web research for personal details and company news
- **Setup**: Google Cloud Platform API key + Custom Search Engine ID
- **Usage**: Research queries for each contact
- **Rate Limits**: 100 queries/day (free tier)

### 4. LinkedIn API (Optional)
- **Purpose**: Professional background research
- **Setup**: LinkedIn Developer Program
- **Note**: Restricted API access, may require alternative approaches
- **Fallback**: Web scraping or public profile data

### 5. Gmail OAuth2
- **Purpose**: Create email drafts
- **Setup**: Google OAuth2 credentials
- **Permissions**: Gmail compose and draft management
- **Safety**: Draft creation only, no sending

### 6. Discord Webhook
- **Purpose**: Team notifications
- **Setup**: Discord server webhook URL
- **Content**: Workflow execution summaries

## Configuration & Best Practices

### Rate Limiting Strategy
- **2-second delays** between companies
- **Continue on fail** for all API nodes
- **Batch size of 1** to prevent overwhelm
- **Timeout handling** with graceful degradation

### Data Quality Controls
- **Email confidence > 70%** threshold
- **Contact validation** (name, email, position required)
- **Email quality checks** (length, personalization, company reference)
- **Duplicate removal** across all sources

### Error Recovery
- **Fallback searches** when primary API fails
- **Partial results handling** (process available data)
- **Error logging** in Notion and Discord
- **Retry logic** for transient failures

### Security Considerations
- **API key management** through n8n credentials
- **No data persistence** outside intended systems
- **Draft-only email creation** prevents accidental sends
- **Audit trail** in Notion for all activities

## Testing & Validation

### Pre-Deployment Testing
1. **Single Company Test**: Run with one company initially
2. **API Validation**: Verify all credentials and endpoints
3. **Output Verification**: Check Notion pages and Gmail drafts
4. **Error Simulation**: Test failure scenarios
5. **Rate Limit Testing**: Ensure delays are sufficient

### Success Metrics
- **Contact Discovery**: 5-10 quality contacts per company
- **Research Quality**: Personal details in 100% of emails
- **Email Standards**: <200 words, highly personalized
- **Error Rate**: <5% failures in contact discovery
- **Processing Time**: <10 minutes per company

### Quality Assurance Checklist
- [ ] All API credentials configured and tested
- [ ] Notion database permissions verified
- [ ] Gmail draft creation (not sending) confirmed
- [ ] Discord notifications working
- [ ] Rate limiting prevents API blocks
- [ ] Error handling gracefully manages failures
- [ ] Output quality meets personalization standards

## Deployment & Operations

### Initial Setup
1. Configure all API credentials in n8n
2. Test with single company in development
3. Verify Notion sub-page creation
4. Confirm Gmail draft creation
5. Test Discord notifications
6. Enable workflow with limited scope

### Monitoring & Maintenance
- **Weekly Review**: Check Discord summaries
- **API Usage**: Monitor rate limits and quotas
- **Quality Control**: Review generated emails periodically
- **Database Cleanup**: Archive old research periodically
- **Credential Rotation**: Update API keys as needed

### Scaling Considerations
- **API Limits**: Monitor Hunter.io and Google quotas
- **Processing Time**: Consider parallel processing for large datasets
- **Storage**: Notion pages may accumulate over time
- **Performance**: Optimize code nodes for efficiency

## Future Enhancements

### Short-term Improvements
- **A/B Testing**: Test different email templates
- **Enhanced Personalization**: More sophisticated research aggregation
- **Better LinkedIn Integration**: Alternative data sources
- **Email Templates**: Multiple personalization strategies

### Long-term Vision
- **AI-Powered Research**: Use LLMs for research analysis
- **Response Tracking**: Monitor email engagement
- **CRM Integration**: Connect with sales pipeline
- **Predictive Scoring**: Score contact likelihood to respond

## Troubleshooting Guide

### Common Issues
1. **Hunter.io Rate Limits**: Implement exponential backoff
2. **Notion API Errors**: Check database permissions
3. **Gmail Authentication**: Refresh OAuth tokens
4. **LinkedIn Restrictions**: Use alternative research methods
5. **Google Search Limits**: Implement query optimization

### Debug Steps
1. Check n8n execution logs
2. Verify API credentials and quotas
3. Test individual nodes in isolation
4. Review Notion page creation
5. Confirm Discord webhook functionality

### Support Resources
- **n8n Documentation**: Node-specific configuration guides
- **API Documentation**: Hunter.io, Notion, Gmail APIs
- **Community Forums**: n8n community for troubleshooting
- **Discord Channel**: Team communication for issues

This workflow represents a comprehensive solution for automated company research and personalized outreach, designed to scale efficiently while maintaining high quality and personalization standards. 