# Amplify Gen 2 Field Types Reference

Based on the official documentation at https://docs.amplify.aws/nextjs/build-a-backend/data/data-modeling/add-fields/

## Supported Field Types

### Scalar Types
- `a.string()` - String values
- `a.integer()` - Integer numbers
- `a.float()` - Floating point numbers
- `a.boolean()` - True/false values
- `a.date()` - Date without time (YYYY-MM-DD)
- `a.time()` - Time without date (HH:MM:SS)
- `a.datetime()` - Date and time
- `a.timestamp()` - Unix timestamp
- `a.email()` - Email addresses with validation
- `a.phone()` - Phone numbers with validation
- `a.url()` - URLs with validation
- `a.ipAddress()` - IP addresses with validation
- `a.json()` - JSON objects

### Special Types
- `a.id()` - Unique identifier
- `a.enum(['value1', 'value2'])` - Enumerated values

### Array Types
- `a.string().array()` - Array of strings
- `a.integer().array()` - Array of integers
- `a.float().array()` - Array of floats
- Other scalar types also support `.array()`

### Field Modifiers
- `.required()` - Field must have a value
- `.default(value)` - Default value for the field
- `.array()` - Makes the field an array

## Relationships
- `a.belongsTo('ModelName', 'foreignKey')` - One-to-one or many-to-one
- `a.hasMany('ModelName', 'foreignKey')` - One-to-many
- `a.hasOne('ModelName', 'foreignKey')` - One-to-one

## Correct Usage Examples

```typescript
const schema = a.schema({
  User: a.model({
    // Scalar fields
    username: a.string().required(),
    email: a.email().required(),
    phone: a.phone(),
    age: a.integer(),
    
    // Arrays
    tags: a.string().array(),
    scores: a.integer().array(),
    
    // JSON for complex data
    preferences: a.json(),
    
    // Relationships
    posts: a.hasMany('Post', 'userId')
  }),
  
  Post: a.model({
    title: a.string().required(),
    content: a.string(),
    publishedAt: a.datetime(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    
    // Enum field
    status: a.enum(['draft', 'published', 'archived'])
  })
});
```

## Important Notes

1. **Email and Phone Types**: `a.email()` and `a.phone()` are supported in Gen 2 and include built-in validation
2. **Arrays**: Use `.array()` modifier instead of JSON workarounds for simple arrays
3. **Complex Objects**: Use `a.json()` for nested objects or complex data structures
4. **Custom Validation**: Can be added through custom business logic in the backend