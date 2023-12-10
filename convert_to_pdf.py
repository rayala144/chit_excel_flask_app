import convertapi

convertapi.api_secret = '9L6ycqIksAnQIyDp'

result = convertapi.convert('pdf', { 'File': 'u_chits_updated.xlsx' })

# save to file
result.file.save('u_chits_converted.pdf')
