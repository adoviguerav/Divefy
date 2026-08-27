r
##### OJO duda aquí
DUDA: se genera un embeddings combinando chunk + contexto? o son dos separados? 
DUDA 2: se genera un embeddings combinando chunk + preguntas? No no? Se generan embeddings de las preguntas, y todas tienen el mismo id de forma que así no se recuperan dos que apuntan al mismo chunk no?

esto es clave para saber como indexar. segun he entendido, si que genera embeddings combinando chunk + contexto, pero no chunk + preguntas. en el caso preguntas, solo preguntas y ya. 

otra cosa, hemos usado un tokenizador diferente para limiatar los chunks de tamaño en la fase 2 y 3. la cosa es, hay algo de diferencia si ahota cambiamos de modelo?. se sipone que los limites de chunks son 50 tokens < tmaaño chunk < 512 tokens. entonces, si los otros modelos de embeddings no tienen un limite más bajo, no habría problema no? por otro lado, si vamos a utilizar varios modelos de embeddings, tenemos que generar dos paquetes de embeddings no?


### Elección de embeddings:
- entonces el modelo está desactualizado no? la idea es que vamos a elegir un modelo de embeddings grande o pequeño? merece la pena comparar rendimeinto de modelo grande vs pequeño? es decir, uno de API como openai con uno que usaríamos ene l caso hardware? (o dos caso hardware). En todo caso, debemos definir: tamaño del vector, multilingue si o si, embeddings de dominio de buceo dudo que haya (podríamos mirar), simétrico o asimétrico y ventana ma´xima
- la idea de probar modelos de API es para poder comparar y ver cuánto varía del caso ideal vs caso local

### noramlizamos?
esto es imp. hay que ver si nooramlizar o no. que formas hay de comparar vectores y cuales necesitan normalizar? cual eleigmos nosotros?

### asignar id
reutilizamos el id del chunk para el embedddings?

### separar el vector, el texto y los datos que lo describen
esto es saber que no indexamos todo. indexamos lo que buscamos, pero ulego mostramos el texto original, y los metadatos dan info extra que sirven para filtrar, no para buscar por signifciado

### donde guardamos?
en una base de datos ligera y vectorial? o mejor, en vez de complciarlo, cual es el caso ideal para el local? es decir, que es la mejor opción o más simple para nuestro caso de uso?. está el array en memoria, una librería como faiss o base de datos vectorial ligera y local. comparamos y elegikmos, me da igual lop que ponga ene l PRD


## Con todo esto, planificar
se que me has puesto mensajes antes, y probablmente me haya dejado cosas, pero quiero que partamos de este reasoning y que añadas o cuestiones cosas que falten que no haya mencionado. la idea es que lo pienses como unnpipeline, para tomar decisiones paso a paso

por otro lado, la fase 3 ya está terminada, por lo que habrá habido cambios, quizá es bueno que lo leas