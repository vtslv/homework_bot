class BadHttpStatus(Exception):
    '''Ошибка. HTTP статус != 200.'''
    
    pass

# class HomeworkStatusValueUnknown(Exception):
#     '''Ошибка. Неизвестный статус ДЗ.'''

#     pass

class SendMessageError(Exception):
    '''Ошибка отправки сообщения.'''

    pass

class UnknownHomeworkStatus(Exception):
    '''Ошибка. Неизвестный статус ДЗ.'''

    pass